import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_map_marker_cluster/flutter_map_marker_cluster.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';

import '../config/map_tiles.dart';
import '../config/theme.dart';
import '../models/client_model.dart';
import '../models/tracking_models.dart';
import '../models/user_model.dart';
import '../services/campaign_service.dart';
import '../services/firestore_service.dart';
import '../utils/responsive.dart';
import '../utils/trail_analysis.dart';
import '../utils/trail_filter.dart';
import '../widgets/adaptive_sheet.dart';
import '../widgets/gestor_day_report_sheet.dart';

/// Admin/supervisor: posición en vivo, recorrido GPS y ruta planificada del equipo.
class TrackingScreen extends StatefulWidget {
  const TrackingScreen({super.key});

  @override
  State<TrackingScreen> createState() => _TrackingScreenState();
}

class _TrackingScreenState extends State<TrackingScreen> {
  final _firestore = FirestoreService();
  final _campaignService = CampaignService();
  final _mapController = MapController();
  final _dateFmt = DateFormat('yyyy-MM-dd');
  final _prettyFmt = DateFormat('dd/MM/yyyy');
  final _trailFilter = TrailFilter();
  final _trailAnalysis = TrailAnalysis(proximityRadiusMeters: 80);

  List<GestorLocation> _gestores = [];
  List<UserModel> _gestorUsers = [];
  StreamSubscription<List<GestorLocation>>? _locationSub;
  GestorLocation? _selectedGestor;
  FilteredTrail _filteredTrail = FilteredTrail.empty();
  List<LatLng> _plannedPoints = [];
  List<ClientModel> _sectionClients = [];
  List<ClientProximityResult> _proximity = [];
  bool _loadingTrail = false;
  bool _loadingClients = false;
  bool _hasPlannedRoute = false;
  double _totalKm = 0;
  String? _sectionFilter;
  DateTime _selectedDay = DateTime.now();
  Map<String, double> _teamKmByUid = {};
  bool _loadingTeamKm = false;
  bool _hasReceivedLocations = false;
  bool _showRawPoints = false;
  bool _showClients = true;

  static const _sectionColors = [
    Color(0xFF4F46E5),
    Color(0xFF0D9488),
    Color(0xFFD97706),
    Color(0xFFDC2626),
    Color(0xFF7C3AED),
    Color(0xFF059669),
    Color(0xFFE11D48),
    Color(0xFF0891B2),
    Color(0xFFB45309),
    Color(0xFF6366F1),
  ];

  final Map<String, Color> _colorMap = {};
  int _tileSourceIndex = 0;

  @override
  void initState() {
    super.initState();
    _loadGestorUsers();
    _locationSub = _firestore.streamGestorLocations().listen(
      _onLocationsUpdate,
      onError: (e) {
        if (!mounted) return;
        setState(() => _hasReceivedLocations = true);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error GPS: $e')),
        );
      },
    );
  }

  @override
  void dispose() {
    _locationSub?.cancel();
    super.dispose();
  }

  Future<void> _loadGestorUsers() async {
    final users = await _firestore.getGestoresActivos();
    if (!mounted) return;
    setState(() => _gestorUsers = users);
    if (_gestores.isNotEmpty) {
      _onLocationsUpdate(_gestores);
    }
  }

  void _onLocationsUpdate(List<GestorLocation> raw) {
    final enriched = raw.map((g) {
      for (final user in _gestorUsers) {
        if (user.uid == g.uid && user.nombre.isNotEmpty) {
          return g.copyWith(nombre: user.nombre);
        }
      }
      return g;
    }).toList();

    final sections = enriched.map((g) => g.seccion).toSet().toList()..sort();
    _colorMap.clear();
    for (var i = 0; i < sections.length; i++) {
      _colorMap[sections[i]] = _sectionColors[i % _sectionColors.length];
    }

    GestorLocation? selected;
    final prevUid = _selectedGestor?.uid;
    if (prevUid != null) {
      for (final g in enriched) {
        if (g.uid == prevUid) {
          selected = g;
          break;
        }
      }
    }

    final hadGestores = _gestores.isNotEmpty;
    setState(() {
      _hasReceivedLocations = true;
      _gestores = enriched;
      _selectedGestor = selected;
    });

    if (!hadGestores && enriched.isNotEmpty) {
      _refreshTeamKmForVisibleGestores();
    }
  }

  String get _fechaDia => _dateFmt.format(_selectedDay);

  List<GestorLocation> get _filteredGestores {
    if (_sectionFilter == null || _sectionFilter!.isEmpty) return _gestores;
    return _gestores.where((g) => g.seccion == _sectionFilter).toList();
  }

  Future<void> _refreshTeamKmForVisibleGestores() async {
    final targets = _filteredGestores.isNotEmpty ? _filteredGestores : _gestores;
    if (targets.isEmpty) return;
    setState(() => _loadingTeamKm = true);
    final kmMap = Map<String, double>.from(_teamKmByUid);
    for (final g in targets) {
      final trail = await _firestore.getTrackingTrail(g.uid, day: _selectedDay);
      kmMap[g.uid] = _trailFilter.filter(trail).km;
    }
    if (!mounted) return;
    setState(() {
      _teamKmByUid = kmMap;
      _loadingTeamKm = false;
    });
  }

  Future<void> _loadTrailAndRoute(String uid) async {
    setState(() {
      _loadingTrail = true;
      _filteredTrail = FilteredTrail.empty();
      _plannedPoints = [];
      _hasPlannedRoute = false;
      _totalKm = 0;
      _proximity = [];
    });

    final trail = await _firestore.getTrackingTrail(uid, day: _selectedDay);
    final filtered = _trailFilter.filter(trail);
    final route = await _firestore.getGestorRouteByDate(uid, _fechaDia);

    var planned = <LatLng>[];
    var hasPlanned = false;
    if (route != null) {
      final raw = (route['clientes'] as List?) ?? const [];
      final clients = raw
          .map((e) =>
              e is Map ? e.map((k, v) => MapEntry(k.toString(), v)) : <String, dynamic>{})
          .where((c) => c['lat'] != null && c['lng'] != null)
          .toList();
      if (clients.isNotEmpty) {
        final ordered = TrackingGeo.orderRouteClients(clients);
        planned = ordered
            .map((c) => LatLng(
                  (c['lat'] as num).toDouble(),
                  (c['lng'] as num).toDouble(),
                ))
            .toList();
        hasPlanned = planned.length >= 2;
      }
    }

    if (!mounted) return;
    setState(() {
      _filteredTrail = filtered;
      _plannedPoints = planned;
      _hasPlannedRoute = hasPlanned;
      _totalKm = filtered.km;
      _loadingTrail = false;
      _teamKmByUid[uid] = filtered.km;
    });

    _fitTrailBounds();
    await _loadSectionClientsAndProximity();
  }

  Future<void> _loadSectionClientsAndProximity() async {
    final g = _selectedGestor;
    if (g == null) return;
    setState(() => _loadingClients = true);

    try {
      final campaignId = await _campaignService.getActiveCampaignId();
      if (campaignId == null || !mounted) {
        setState(() {
          _sectionClients = [];
          _proximity = [];
          _loadingClients = false;
        });
        return;
      }

      final section = g.seccion;
      final clients = await _firestore.getClientsWithCoordinates(
        campaignId,
        section,
        limit: 400,
      );
      final active = clients.where((c) => c.isActiveForGestor).toList();
      final proximity = _trailAnalysis.analyze(
        trail: _filteredTrail,
        clients: active,
      );

      if (!mounted) return;
      setState(() {
        _sectionClients = active;
        _proximity = proximity;
        _loadingClients = false;
      });
    } catch (e) {
      debugPrint('loadSectionClients: $e');
      if (!mounted) return;
      setState(() {
        _sectionClients = [];
        _proximity = [];
        _loadingClients = false;
      });
    }
  }

  void _selectGestor(GestorLocation gestor) {
    setState(() => _selectedGestor = gestor);
    _loadTrailAndRoute(gestor.uid);
  }

  void _clearSelection() {
    setState(() {
      _selectedGestor = null;
      _filteredTrail = FilteredTrail.empty();
      _plannedPoints = [];
      _hasPlannedRoute = false;
      _totalKm = 0;
      _sectionClients = [];
      _proximity = [];
    });
    if (_filteredGestores.isNotEmpty) _fitBounds(_filteredGestores);
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDay,
      firstDate: DateTime.now().subtract(const Duration(days: 90)),
      lastDate: DateTime.now(),
      locale: const Locale('es', 'PE'),
    );
    if (picked == null || !mounted) return;
    setState(() => _selectedDay = picked);
    await _refreshTeamKmForVisibleGestores();
    if (_selectedGestor != null) {
      await _loadTrailAndRoute(_selectedGestor!.uid);
    }
  }

  void _fitBounds(List<GestorLocation> list) {
    if (list.isEmpty) return;
    final lats = list.map((g) => g.lat);
    final lngs = list.map((g) => g.lng);
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds(
          LatLng(lats.reduce((a, b) => a < b ? a : b), lngs.reduce((a, b) => a < b ? a : b)),
          LatLng(lats.reduce((a, b) => a > b ? a : b), lngs.reduce((a, b) => a > b ? a : b)),
        ),
        padding: const EdgeInsets.all(50),
      ),
    );
  }

  void _fitTrailBounds() {
    final points = <LatLng>[];
    for (final seg in _filteredTrail.segments) {
      for (final p in seg) {
        points.add(LatLng(p.lat, p.lng));
      }
    }
    for (final v in _filteredTrail.visitPoints) {
      points.add(LatLng(v.lat, v.lng));
    }
    if (points.isEmpty) {
      final g = _selectedGestor;
      if (g != null) {
        _mapController.move(LatLng(g.lat, g.lng), 15);
      }
      return;
    }
    if (points.length == 1) {
      _mapController.move(points.first, 15);
      return;
    }
    final lats = points.map((p) => p.latitude);
    final lngs = points.map((p) => p.longitude);
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds(
          LatLng(lats.reduce((a, b) => a < b ? a : b), lngs.reduce((a, b) => a < b ? a : b)),
          LatLng(lats.reduce((a, b) => a > b ? a : b), lngs.reduce((a, b) => a > b ? a : b)),
        ),
        padding: const EdgeInsets.all(60),
      ),
    );
  }

  void _focusMapPoint(LatLng point) {
    _mapController.move(point, 16);
  }

  void _openReport() {
    final g = _selectedGestor;
    if (g == null) return;
    AdaptiveSheet.show(
      context: context,
      title: null,
      maxWidth: 560,
      builder: (ctx) => GestorDayReportSheet(
        gestorNombre: g.nombre,
        fechaDia: _prettyFmt.format(_selectedDay),
        filtered: _filteredTrail,
        proximity: _proximity,
        onFocusPoint: _focusMapPoint,
      ),
    );
  }

  double get _teamTotalKm =>
      _teamKmByUid.values.fold(0.0, (acc, km) => acc + km);

  bool _clientManagedToday(ClientModel c) {
    if (c.isPendiente) return false;
    if (c.fechaGestion.isEmpty) return !c.isPendiente;
    return c.fechaGestion.startsWith(_fechaDia);
  }

  Color _clientMarkerColor(ClientModel c) {
    ClientProximityResult? prox;
    for (final r in _proximity) {
      if (r.client.id == c.id) {
        prox = r;
        break;
      }
    }
    if (prox?.status == ClientTrailStatus.managed || _clientManagedToday(c)) {
      return AppTheme.success;
    }
    if (prox?.status == ClientTrailStatus.nearbyWithoutVisit) {
      return AppTheme.warning;
    }
    if (!c.isPendiente) return AppTheme.info;
    return AppTheme.statusPendiente;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Recorridos en campo'),
        actions: [
          IconButton(
            icon: Icon(
              _showClients ? Icons.people_alt : Icons.people_alt_outlined,
              color: Colors.white,
            ),
            tooltip: _showClients ? 'Ocultar clientes' : 'Mostrar clientes',
            onPressed: () => setState(() => _showClients = !_showClients),
          ),
          IconButton(
            icon: Icon(
              _showRawPoints ? Icons.bug_report : Icons.bug_report_outlined,
              color: Colors.white,
            ),
            tooltip: _showRawPoints
                ? 'Ocultar puntos descartados'
                : 'Mostrar puntos descartados',
            onPressed: () => setState(() => _showRawPoints = !_showRawPoints),
          ),
          IconButton(
            icon: const Icon(Icons.calendar_today_outlined, color: Colors.white),
            tooltip: 'Fecha',
            onPressed: _pickDate,
          ),
          PopupMenuButton<int>(
            tooltip: 'Proveedor de mapa',
            onSelected: (idx) {
              MapTilesConfig.resetTileErrors();
              setState(() => _tileSourceIndex = idx);
            },
            itemBuilder: (_) => MapTilesConfig.buildSourceMenuItems(),
            icon: const Icon(Icons.layers_outlined, color: Colors.white),
          ),
          if (_selectedGestor != null)
            IconButton(
              icon: const Icon(Icons.close, color: Colors.white),
              tooltip: 'Limpiar selección',
              onPressed: _clearSelection,
            ),
        ],
      ),
      body: !_hasReceivedLocations
          ? const Center(
              child: CircularProgressIndicator(color: AppTheme.primaryColor),
            )
          : _gestores.isEmpty
              ? _buildEmpty()
              : Column(
                  children: [
                    _buildTeamSummaryBar(_filteredGestores),
                    _buildDateAndFilterBar(_filteredGestores),
                    if (_selectedGestor != null) _buildInfoBar(),
                    Expanded(child: _buildTrackingLayout(_filteredGestores)),
                  ],
                ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.location_off_outlined, size: 64, color: Colors.grey.shade300),
          const SizedBox(height: 16),
          Text(
            'Sin gestores con GPS activo',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade500,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Los gestores deben tener la app abierta con GPS activo.\n'
            'Vuelva a comprobar en horario de campo.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey.shade400, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildTeamSummaryBar(List<GestorLocation> visible) {
    final totalKm = visible.isEmpty
        ? _teamTotalKm
        : visible.fold(0.0, (s, g) => s + (_teamKmByUid[g.uid] ?? 0));

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: AppTheme.primaryColor.withValues(alpha: 0.06),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _prettyFmt.format(_selectedDay),
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                ),
                Text(
                  _loadingTeamKm
                      ? 'Calculando km del equipo…'
                      : '${visible.length} gestores · ${totalKm.toStringAsFixed(1)} km total',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                ),
              ],
            ),
          ),
          if (_hasPlannedRoute && _selectedGestor != null)
            _legendChip('Planificada', Colors.grey.shade600, dashed: true),
          const SizedBox(width: 6),
          if (_filteredTrail.segments.any((s) => s.length >= 2))
            _legendChip('Recorrido GPS', AppTheme.primaryColor),
          if (_showClients && _sectionClients.isNotEmpty) ...[
            const SizedBox(width: 6),
            _legendChip('Clientes', AppTheme.info),
          ],
        ],
      ),
    );
  }

  Widget _legendChip(String label, Color color, {bool dashed = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.5)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 16,
            height: 3,
            decoration: BoxDecoration(
              color: dashed ? Colors.transparent : color,
              border: dashed ? Border(bottom: BorderSide(color: color, width: 2)) : null,
            ),
          ),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 10, color: color)),
        ],
      ),
    );
  }

  Widget _buildDateAndFilterBar(List<GestorLocation> visible) {
    final sections = _gestores.map((g) => g.seccion).toSet().toList()..sort();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: DropdownButtonFormField<String?>(
              value: _sectionFilter,
              decoration: const InputDecoration(
                labelText: 'Sección',
                isDense: true,
                contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              ),
              items: [
                const DropdownMenuItem(value: null, child: Text('Todas')),
                ...sections.map(
                  (s) => DropdownMenuItem(value: s, child: Text('Sección $s')),
                ),
              ],
              onChanged: (v) {
                setState(() => _sectionFilter = v);
                _refreshTeamKmForVisibleGestores();
              },
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            tooltip: 'Actualizar km del día',
            onPressed: _loadingTeamKm ? null : _refreshTeamKmForVisibleGestores,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoBar() {
    final g = _selectedGestor!;
    final color = _colorMap[g.seccion] ?? AppTheme.primaryColor;
    final rejected = _filteredTrail.rejected.length;
    final visits = _filteredTrail.visitPoints.length;
    final nearby = _proximity.where((p) => p.passedNearby).length;

    return Container(
      color: color.withValues(alpha: 0.08),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: color,
            child: Text(
              g.seccion,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        g.nombre,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (g.isOnline) ...[
                      const SizedBox(width: 6),
                      Container(
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          color: AppTheme.success,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const Text(' en línea', style: TextStyle(fontSize: 10, color: AppTheme.success)),
                    ],
                  ],
                ),
                if (_loadingTrail)
                  Text(
                    'Cargando recorrido…',
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
                  )
                else
                  Text(
                    '${_filteredTrail.pointCount} pts'
                    '${rejected > 0 ? ' · $rejected desc.' : ''}'
                    ' · ${_totalKm.toStringAsFixed(2)} km'
                    '${visits > 0 ? ' · $visits gest.' : ''}'
                    '${nearby > 0 ? ' · $nearby sin gest.' : ''}'
                    '${_hasPlannedRoute ? ' · planificada' : ''}',
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                  ),
              ],
            ),
          ),
          TextButton.icon(
            onPressed: _loadingTrail ? null : _openReport,
            icon: const Icon(Icons.assessment_outlined, size: 18),
            label: const Text('Reporte'),
            style: TextButton.styleFrom(
              foregroundColor: color,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              visualDensity: VisualDensity.compact,
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              '${_totalKm.toStringAsFixed(1)} km',
              style: TextStyle(fontWeight: FontWeight.w700, color: color, fontSize: 13),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 200.ms).slideY(begin: -0.3, end: 0);
  }

  Widget _buildMap(List<GestorLocation> visible) {
    final defaultCenter = const LatLng(-12.0464, -77.0428);
    final center = _selectedGestor != null
        ? LatLng(_selectedGestor!.lat, _selectedGestor!.lng)
        : (visible.isNotEmpty
            ? LatLng(visible.first.lat, visible.first.lng)
            : defaultCenter);

    final trailColor =
        (_colorMap[_selectedGestor?.seccion] ?? AppTheme.primaryColor)
            .withValues(alpha: 0.85);

    final segmentPolylines = <Polyline>[];
    for (final seg in _filteredTrail.segments) {
      if (seg.length < 2) continue;
      segmentPolylines.add(Polyline(
        points: seg.map((p) => LatLng(p.lat, p.lng)).toList(),
        color: trailColor,
        strokeWidth: 4,
      ));
    }

    return FlutterMap(
      mapController: _mapController,
      options: MapOptions(
        initialCenter: center,
        initialZoom: _selectedGestor != null ? 15 : 12,
        minZoom: 3,
        maxZoom: 18,
        onMapReady: () {
          refreshMapTiles(_mapController);
          if (_selectedGestor != null && _filteredTrail.kept.isNotEmpty) {
            _fitTrailBounds();
          } else if (_selectedGestor == null && visible.isNotEmpty) {
            _fitBounds(visible);
          }
        },
      ),
      children: [
        MapTilesConfig.buildTileLayer(sourceIndex: _tileSourceIndex),
        if (_selectedGestor != null && _selectedGestor!.accuracy > 0)
          CircleLayer(
            circles: [
              CircleMarker(
                point: LatLng(_selectedGestor!.lat, _selectedGestor!.lng),
                radius: _selectedGestor!.accuracy.clamp(5, 200),
                useRadiusInMeter: true,
                color: trailColor.withValues(alpha: 0.12),
                borderColor: trailColor.withValues(alpha: 0.4),
                borderStrokeWidth: 1,
              ),
            ],
          ),
        if (_plannedPoints.length >= 2)
          PolylineLayer(
            polylines: [
              Polyline(
                points: _plannedPoints,
                color: Colors.grey.shade600,
                strokeWidth: 3,
                pattern: StrokePattern.dashed(segments: [12, 8]),
              ),
            ],
          ),
        if (segmentPolylines.isNotEmpty)
          PolylineLayer(polylines: segmentPolylines),
        if (_showRawPoints && _filteredTrail.rejected.isNotEmpty)
          MarkerLayer(
            markers: _filteredTrail.rejected
                .map(
                  (r) => Marker(
                    point: LatLng(r.point.lat, r.point.lng),
                    width: 10,
                    height: 10,
                    child: Container(
                      decoration: BoxDecoration(
                        color: Colors.grey.shade500.withValues(alpha: 0.7),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                )
                .toList(),
          ),
        if (_filteredTrail.stays.isNotEmpty)
          MarkerLayer(
            markers: _filteredTrail.stays.map((s) {
              final mins = s.duration.inMinutes;
              return Marker(
                point: LatLng(s.lat, s.lng),
                width: 36,
                height: 36,
                child: Tooltip(
                  message: 'Parada $mins min',
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.warning,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                    child: const Icon(Icons.pause, color: Colors.white, size: 16),
                  ),
                ),
              );
            }).toList(),
          ),
        if (_filteredTrail.kept.isNotEmpty && _selectedGestor != null)
          MarkerLayer(
            markers: _buildTrailEndpointMarkers(),
          ),
        if (_showClients && _sectionClients.isNotEmpty) _buildClientClusterLayer(),
        MarkerLayer(
          markers: visible.map((g) {
            final color = _colorMap[g.seccion] ?? AppTheme.primaryColor;
            final isSelected = _selectedGestor?.uid == g.uid;
            return Marker(
              point: LatLng(g.lat, g.lng),
              width: isSelected ? 48 : 40,
              height: isSelected ? 48 : 40,
              child: GestureDetector(
                onTap: () => _selectGestor(g),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: isSelected ? 40 : 34,
                      height: isSelected ? 40 : 34,
                      decoration: BoxDecoration(
                        color: isSelected ? color : color.withValues(alpha: 0.9),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: isSelected ? Colors.white : Colors.white70,
                          width: isSelected ? 3 : 2,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: color.withValues(alpha: isSelected ? 0.5 : 0.3),
                            blurRadius: isSelected ? 12 : 6,
                          ),
                        ],
                      ),
                      child: Center(
                        child: Text(
                          g.seccion,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ),
                    if (g.isOnline)
                      Container(
                        margin: const EdgeInsets.only(top: 2),
                        width: 6,
                        height: 6,
                        decoration: const BoxDecoration(
                          color: AppTheme.success,
                          shape: BoxShape.circle,
                        ),
                      ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
        MapTilesConfig.buildAttribution(_tileSourceIndex),
      ],
    );
  }

  List<Marker> _buildTrailEndpointMarkers() {
    final kept = _filteredTrail.kept;
    if (kept.isEmpty) return const [];
    final markers = <Marker>[];

    final first = kept.first;
    final last = kept.last;
    markers.add(Marker(
      point: LatLng(first.lat, first.lng),
      width: 28,
      height: 28,
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.success,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2),
        ),
        child: const Icon(Icons.play_arrow, color: Colors.white, size: 16),
      ),
    ));
    if (kept.length > 1) {
      markers.add(Marker(
        point: LatLng(last.lat, last.lng),
        width: 28,
        height: 28,
        child: Container(
          decoration: BoxDecoration(
            color: AppTheme.danger,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
          ),
          child: const Icon(Icons.flag, color: Colors.white, size: 16),
        ),
      ));
    }
    for (final p in kept) {
      if (!p.isVisit) continue;
      markers.add(Marker(
        point: LatLng(p.lat, p.lng),
        width: 22,
        height: 22,
        child: Tooltip(
          message: [
            if (p.cliente.isNotEmpty) p.cliente,
            if (p.estado.isNotEmpty) p.estado,
          ].join(' · '),
          child: Container(
            decoration: BoxDecoration(
              color: AppTheme.getStatusColor(p.estado),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 2),
            ),
            child: const Icon(Icons.location_on, color: Colors.white, size: 12),
          ),
        ),
      ));
    }
    return markers;
  }

  Widget _buildClientClusterLayer() {
    final markers = _sectionClients.map((c) {
      final color = _clientMarkerColor(c);
      return Marker(
        point: LatLng(c.latitude, c.longitude),
        width: 36,
        height: 36,
        child: GestureDetector(
          onTap: () => _showClientPopup(c),
          child: Icon(Icons.place, color: color, size: 28),
        ),
      );
    }).toList();

    if (markers.length >= 40) {
      return MarkerClusterLayerWidget(
        options: MarkerClusterLayerOptions(
          maxClusterRadius: 45,
          size: const Size(40, 40),
          markers: markers,
          builder: (context, clusterMarkers) {
            return Container(
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppTheme.info,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2),
              ),
              child: Text(
                '${clusterMarkers.length}',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            );
          },
        ),
      );
    }
    return MarkerLayer(markers: markers);
  }

  void _showClientPopup(ClientModel c) {
    ClientProximityResult? prox;
    for (final r in _proximity) {
      if (r.client.id == c.id) {
        prox = r;
        break;
      }
    }
    String proximLabel = 'Sin análisis';
    if (prox != null) {
      switch (prox.status) {
        case ClientTrailStatus.managed:
          proximLabel = 'Gestionado hoy';
        case ClientTrailStatus.nearbyWithoutVisit:
          proximLabel =
              'Pasó a ${prox.minDistanceMeters.toStringAsFixed(0)} m sin gestionar';
        case ClientTrailStatus.notApproached:
          proximLabel = 'No se acercó';
      }
    }

    showModalBottomSheet(
      context: context,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              c.displayName,
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
            ),
            const SizedBox(height: 4),
            Text(
              c.fullAddress.isNotEmpty ? c.fullAddress : 'Sin dirección',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 8),
            Chip(
              label: Text(c.estadoGestion),
              backgroundColor:
                  AppTheme.getStatusColor(c.estadoGestion).withValues(alpha: 0.15),
              labelStyle: TextStyle(
                color: AppTheme.getStatusColor(c.estadoGestion),
                fontSize: 12,
              ),
            ),
            Text(
              proximLabel,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            if (_loadingClients)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: LinearProgressIndicator(),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildTrackingLayout(List<GestorLocation> visible) {
    if (context.isExpanded) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(flex: 2, child: _buildMap(visible)),
          const VerticalDivider(width: 1),
          Expanded(flex: 1, child: _buildGestorSideList(visible)),
        ],
      );
    }
    return Column(
      children: [
        Expanded(child: _buildMap(visible)),
        _buildGestorList(visible),
      ],
    );
  }

  Widget _buildGestorSideList(List<GestorLocation> visible) {
    return ColoredBox(
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
            child: Text(
              '${visible.length} gestores · toque para ver recorrido',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              itemCount: visible.length,
              itemBuilder: (context, i) {
                final g = visible[i];
                final color = _colorMap[g.seccion] ?? AppTheme.primaryColor;
                final isSelected = _selectedGestor?.uid == g.uid;
                final km = _teamKmByUid[g.uid];
                return Card(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: isSelected ? color : Colors.grey.shade200,
                      width: isSelected ? 2 : 1,
                    ),
                  ),
                  child: InkWell(
                    onTap: () => _selectGestor(g),
                    mouseCursor: SystemMouseCursors.click,
                    child: Padding(
                      padding: const EdgeInsets.all(10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  g.nombre,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                              if (g.isOnline)
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(
                                    color: AppTheme.success,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            g.seccion,
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey.shade600,
                            ),
                          ),
                          if (km != null) ...[
                            const SizedBox(height: 4),
                            Text(
                              '${km.toStringAsFixed(1)} km',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: color,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGestorList(List<GestorLocation> visible) {
    return Container(
      height: 118,
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 16, top: 8, bottom: 4),
            child: Text(
              '${visible.length} gestores · toque para ver recorrido',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade500,
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: visible.length,
              itemBuilder: (context, i) {
                final g = visible[i];
                final color = _colorMap[g.seccion] ?? AppTheme.primaryColor;
                final isSelected = _selectedGestor?.uid == g.uid;
                final km = _teamKmByUid[g.uid];
                return GestureDetector(
                  onTap: () => _selectGestor(g),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    width: 140,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? color.withValues(alpha: 0.1)
                          : Colors.grey.shade50,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isSelected ? color : Colors.grey.shade200,
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          children: [
                            CircleAvatar(
                              radius: 10,
                              backgroundColor: color,
                              child: Text(
                                g.seccion,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 9,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                g.nombre.split(' ').first,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 12,
                                  color:
                                      isSelected ? color : AppTheme.textPrimary,
                                ),
                              ),
                            ),
                            if (g.isOnline)
                              const Icon(Icons.circle, size: 8, color: AppTheme.success),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          km != null
                              ? '${km.toStringAsFixed(1)} km · ${_formatTimestamp(g.timestamp)}'
                              : _formatTimestamp(g.timestamp),
                          style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String _formatTimestamp(Timestamp? ts) {
    if (ts == null) return 'Sin datos';
    final dt = ts.toDate();
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 5) return 'Ahora';
    if (diff.inMinutes < 60) return 'Hace ${diff.inMinutes} min';
    if (diff.inHours < 24) return 'Hace ${diff.inHours}h';
    return '${dt.day}/${dt.month} ${dt.hour}:${dt.minute.toString().padLeft(2, '0')}';
  }
}
