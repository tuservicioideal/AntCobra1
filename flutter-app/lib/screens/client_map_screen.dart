import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_map_marker_cluster/flutter_map_marker_cluster.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/map_tiles.dart';
import '../config/theme.dart';
import '../widgets/map_client_marker.dart';
import '../widgets/map_visibility_scope.dart';
import '../models/client_model.dart';
import '../services/auth_service.dart';
import '../services/campana_banco_filter_notifier.dart';
import '../services/campaign_service.dart';
import '../services/firestore_service.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/client_list_pagination.dart';
import '../widgets/campana_banco_filter_bar.dart';
import '../widgets/client_list_pagination_bar.dart';
import '../services/location_service.dart';
import '../services/route_refresh_service.dart';
import '../utils/map_error_logger.dart';
import '../utils/responsive.dart';
import '../utils/section_utils.dart';
import '../widgets/adaptive_sheet.dart';
import 'client_detail_screen.dart';

/// Valor especial del selector para ver todas las secciones asignadas al gestor.
const _allMySectionsKey = '__all_my_sections__';
const _sectionMetaTimeout = Duration(seconds: 8);
const _mapTapHintPrefsKey = 'client_map_tap_hint_dismissed';
const _overlapDistanceM = 25.0;
const _listCardExtent = 196.0;
const _clusterMinClients = 40;
const _distance = Distance();

class ClientMapScreen extends StatefulWidget {
  const ClientMapScreen({super.key});

  @override
  State<ClientMapScreen> createState() => _ClientMapScreenState();
}

class _ClientMapScreenState extends State<ClientMapScreen>
    with MapTabVisibilityMixin {
  final _campaignService = CampaignService();
  final _firestoreService = FirestoreService();
  final _locationService = LocationService();
  final _db = FirebaseFirestore.instance;
  final _mapController = MapController();
  final _listScrollController = ScrollController();
  final _searchController = TextEditingController();
  final _dateFormat = DateFormat('yyyy-MM-dd');

  String? _campaignId;
  List<Map<String, dynamic>> _sections = [];
  String? _selectedSection;
  List<ClientModel> _clients = [];
  List<ClientModel> _filtered = [];
  final Set<String> _selectedIds = <String>{};
  bool _loading = true;
  bool _loadingClients = false;
  bool _savingRoute = false;
  String _query = '';
  ClientModel? _selectedClient;
  DateTime _routeDate = DateTime.now();
  String? _saveMsg;
  String? _loadError;
  int _tileSourceIndex = 0;
  bool _drawingZone = false;
  final List<LatLng> _drawnZonePoints = [];
  LatLng? _myPosition;
  String? _positionHint;
  List<String> _gestorSectionKeys = [];
  bool _mapDataLoadStarted = false;
  bool _awaitingTabActivation = true;
  bool _showMapTapHint = true;
  String? _lastToggledClientId;
  final _listPagination = ClientListPagination();
  CampanaBancoFilterNotifier? _campanaFilterNotifier;

  @override
  MapController get mapControllerForRefresh => _mapController;

  @override
  void onMapTabFirstVisible() {
    _ensureMapDataLoaded();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final notifier = context.read<CampanaBancoFilterNotifier>();
    if (_campanaFilterNotifier != notifier) {
      _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);
      _campanaFilterNotifier = notifier;
      _campanaFilterNotifier!.addListener(_onCampanaFilterChanged);
    }
  }

  void _onCampanaFilterChanged() {
    _applySearch(_query);
  }

  @override
  void initState() {
    super.initState();
    _loading = false;
    MapTilesConfig.tileErrorCount.addListener(_onTileErrorsChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (isMapTabActive) {
        _ensureMapDataLoaded();
      }
    });
    unawaited(_loadMapTapHint());
  }

  Future<void> _loadMapTapHint() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() => _showMapTapHint = !(prefs.getBool(_mapTapHintPrefsKey) ?? false));
  }

  Future<void> _dismissMapTapHint() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_mapTapHintPrefsKey, true);
    if (!mounted) return;
    setState(() => _showMapTapHint = false);
  }

  void _onTileErrorsChanged() {
    if (mounted) setState(() {});
  }

  void _selectTileProvider(int index) {
    MapTilesConfig.resetTileErrors();
    bumpTileLayerGeneration();
    setState(() => _tileSourceIndex = index);
  }

  void _cycleTileProvider() {
    final next = (_tileSourceIndex + 1) % MapTilesConfig.sources.length;
    _selectTileProvider(next);
  }

  void _ensureMapDataLoaded() {
    if (_mapDataLoadStarted) return;
    _mapDataLoadStarted = true;
    _awaitingTabActivation = false;
    unawaited(_loadInitial());
    unawaited(_syncMyPosition());
  }

  /// Usa posición ya cacheada por HomeShell; solo pide GPS si hace falta.
  Future<void> _syncMyPosition() async {
    var lat = _locationService.latitude;
    var lng = _locationService.longitude;
    if (lat != null && lng != null) {
      if (!mounted) return;
      setState(() {
        _myPosition = LatLng(lat!, lng!);
        _positionHint = null;
      });
      _fitToMarkers();
      return;
    }

    final position = await _locationService.getCurrentPosition();
    if (!mounted) return;
    lat = position?.latitude ?? _locationService.latitude;
    lng = position?.longitude ?? _locationService.longitude;
    if (lat != null && lng != null) {
      setState(() {
        _myPosition = LatLng(lat!, lng!);
        _positionHint = null;
      });
      _fitToMarkers();
      return;
    }

    setState(() {
      _positionHint =
          _locationService.error ?? 'Activa el GPS para ver tu ubicación en el mapa.';
    });
  }

  Future<Map<String, dynamic>> _loadSectionMeta(String campaignId, String key) async {
    try {
      final doc = await _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(key)
          .get()
          .timeout(_sectionMetaTimeout);
      if (doc.exists && doc.data() != null) {
        return {'id': key, ...doc.data()!};
      }
    } catch (e, st) {
      MapErrorLogger.log('section_meta:$key', e, st);
    }
    return {'id': key, 'clientes_con_coordenadas': 0, 'num_clientes': 0};
  }

  Future<List<Map<String, dynamic>>> _loadSectionsMetaParallel(
    String campaignId,
    List<String> sectionIds,
  ) async {
    if (sectionIds.isEmpty) return [];
    final metas = await Future.wait(
      sectionIds.map((key) => _loadSectionMeta(campaignId, key)),
    );
    metas.sort((a, b) => (a['id'] as String).compareTo(b['id'] as String));
    return metas;
  }

  List<Map<String, dynamic>> _withAllMySectionsOption(
    List<Map<String, dynamic>> sections,
    List<String> assignedKeys,
  ) {
    if (assignedKeys.length <= 1) return sections;
    final result = List<Map<String, dynamic>>.from(sections);
    result.insert(0, {
      'id': _allMySectionsKey,
      'clientes_con_coordenadas': sections.fold<int>(
        0,
        (sum, s) => sum + ((s['clientes_con_coordenadas'] as num?)?.toInt() ?? 0),
      ),
      'num_clientes': sections.fold<int>(
        0,
        (sum, s) => sum + ((s['num_clientes'] as num?)?.toInt() ?? 0),
      ),
    });
    return result;
  }

  @override
  void dispose() {
    _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);
    MapTilesConfig.tileErrorCount.removeListener(_onTileErrorsChanged);
    _listScrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadInitial() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _loadError = null;
    });

    try {
      final campaignId = await _campaignService.getActiveCampaignId();
      if (campaignId == null) {
        if (!mounted) return;
        setState(() {
          _campaignId = null;
          _sections = [];
          _selectedSection = null;
        });
        return;
      }
      if (!mounted) return;

      final auth = context.read<AuthService>();
      final profile = auth.profile;
      final isGestor = profile?.isGestor ?? false;

      List<Map<String, dynamic>> sections;
      if (isGestor) {
        final allSectionIds =
            await _campaignService.getAvailableSections(campaignId);
        final assignedSections =
            resolveGestorSectionKeysForCampaign(profile, allSectionIds);
        _gestorSectionKeys = assignedSections;

        if (assignedSections.isEmpty) {
          sections = [];
        } else {
          final metas =
              await _loadSectionsMetaParallel(campaignId, assignedSections);
          sections = _withAllMySectionsOption(metas, assignedSections);
        }
      } else {
        final sectionIds =
            await _campaignService.getAvailableSections(campaignId);
        if (sectionIds.isEmpty) {
          sections = [];
        } else {
          sections = await _loadSectionsMetaParallel(campaignId, sectionIds);
        }
      }

      if (!mounted) return;
      final selected =
          sections.isNotEmpty ? sections.first['id'] as String : null;

      setState(() {
        _campaignId = campaignId;
        _sections = sections;
        _selectedSection = selected;
      });

      await MapErrorLogger.clearLastError();

      if (selected != null) {
        await _loadSectionClients(selected);
      }
    } catch (e, st) {
      MapErrorLogger.log('load_initial', e, st);
      await MapErrorLogger.persistLastError('load_initial', e);
      if (!mounted) return;
      setState(() {
        _loadError =
            'No se pudo cargar el mapa. Verifica internet e intenta nuevamente.';
        _sections = [];
        _selectedSection = null;
      });
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _loadSectionClients(String sectionId) async {
    if (_campaignId == null) return;
    setState(() {
      _loadingClients = true;
      _selectedClient = null;
      _loadError = null;
    });
    try {
      final List<ClientModel> clients;
      if (sectionId == _allMySectionsKey) {
        clients = await _firestoreService.getClientsWithCoordinatesMultiSection(
          _campaignId!,
          _gestorSectionKeys,
        );
      } else {
        clients = await _firestoreService.getClientsWithCoordinates(
          _campaignId!,
          sectionId,
          limit: 250,
        );
      }

      if (!mounted) return;
      final active = clients.where((c) => c.isActiveForGestor).toList();
      context.read<CampanaBancoFilterNotifier>().updateAvailable(active);
      setState(() {
        _selectedSection = sectionId;
        _clients = active;
        _selectedIds.removeWhere((id) => !_clients.any((c) => c.id == id));
        _saveMsg = null;
        _loadingClients = false;
      });
      _applySearch(_query);
      _fitToMarkers();
    } catch (e, st) {
      MapErrorLogger.log('load_section_clients', e, st);
      await MapErrorLogger.persistLastError('load_section_clients', e);
      if (!mounted) return;
      setState(() {
        _clients = [];
        _filtered = [];
        _loadingClients = false;
        _loadError =
            'No se pudo cargar los clientes. Verifica internet e intenta nuevamente.';
      });
    }
  }

  void _applySearch(String q) {
    if (!mounted) return;
    final query = q.trim().toLowerCase();
    final campanaFilter =
        context.read<CampanaBancoFilterNotifier>().selected;
    _query = q;
    var base = applyCampanaBancoFilter(_clients, campanaFilter);
    _listPagination.reset();
    if (query.isEmpty) {
      setState(() => _filtered = base);
      return;
    }
    setState(() {
      _filtered = base
          .where((c) => matchesClientSearch(c, q))
          .toList();
    });
  }

  ClientModel? _clientById(String? id) {
    if (id == null) return null;
    for (final c in _filtered) {
      if (c.id == id) return c;
    }
    return null;
  }

  List<ClientModel> _clientsNear(ClientModel anchor) {
    final anchorPoint = LatLng(anchor.latitude, anchor.longitude);
    return _filtered.where((other) {
      final otherPoint = LatLng(other.latitude, other.longitude);
      final meters = _distance.as(LengthUnit.Meter, anchorPoint, otherPoint);
      return meters <= _overlapDistanceM;
    }).toList();
  }

  void _onMarkerTap(ClientModel client) {
    if (_drawingZone) return;

    final nearby = _clientsNear(client);
    if (nearby.length > 1) {
      _showOverlapPicker(nearby);
      return;
    }
    _toggleClientWithFeedback(client);
  }

  void _onClusterMarkerTap(Marker marker) {
    final id = marker.key is ValueKey<String>
        ? (marker.key! as ValueKey<String>).value
        : null;
    final client = _clientById(id);
    if (client != null) _onMarkerTap(client);
  }

  void _toggleClientWithFeedback(ClientModel client) {
    final added = !_selectedIds.contains(client.id);
    setState(() {
      if (added) {
        _selectedIds.add(client.id);
      } else {
        _selectedIds.remove(client.id);
      }
      _selectedClient = client;
      _lastToggledClientId = client.id;
      _saveMsg = null;
    });
    _showSelectionFeedback(client, added: added);
    _scrollListToClient(client.id);
    _focusClientOnMap(client);
  }

  void _focusClientOnMap(ClientModel client) {
    final zoom = _mapController.camera.zoom;
    _mapController.move(
      LatLng(client.latitude, client.longitude),
      zoom < 14 ? 15 : zoom,
    );
  }

  void _showSelectionFeedback(ClientModel client, {required bool added}) {
    final name = client.displayName.length > 40
        ? '${client.displayName.substring(0, 40)}…'
        : client.displayName;
    final count = _selectedIds.length;
    final toggledId = client.id;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        duration: const Duration(milliseconds: 2000),
        content: Text(
          added
              ? '$name agregado a la ruta ($count)'
              : '$name quitado de la ruta ($count)',
        ),
        action: SnackBarAction(
          label: 'Deshacer',
          onPressed: () {
            if (_lastToggledClientId != toggledId) return;
            final c = _clientById(toggledId);
            if (c != null) _toggleClientWithFeedback(c);
          },
        ),
      ),
    );
  }

  Future<void> _showOverlapPicker(List<ClientModel> clients) async {
    if (!mounted) return;
    final searchController = TextEditingController();
    final pagination = ClientListPagination();
    var query = '';

    List<ClientModel> filtered() {
      if (query.trim().isEmpty) return clients;
      return clients.where((c) => matchesClientSearch(c, query)).toList();
    }

    await AdaptiveSheet.show<void>(
      context: context,
      title: 'Varios clientes en este punto',
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final visible = pagination.slice(filtered());
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.only(
                  bottom: MediaQuery.viewInsetsOf(context).bottom,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                      child: Text(
                        'Varios clientes en este punto',
                        style: Theme.of(ctx).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: TextField(
                        controller: searchController,
                        decoration: const InputDecoration(
                          hintText: 'Buscar por nombre o código…',
                          prefixIcon: Icon(Icons.search),
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                        onChanged: (v) => setSheetState(() {
                          query = v;
                          pagination.reset();
                        }),
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.fromLTRB(16, 4, 16, 4),
                      child: Text(
                        'Elige a quién agregar o quitar de tu ruta.',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ),
                    Flexible(
                      child: ListView.builder(
                        shrinkWrap: true,
                        itemCount: visible.length,
                        itemBuilder: (_, i) {
                          final c = visible[i];
                          final onRoute = _selectedIds.contains(c.id);
                          return ListTile(
                            leading: Icon(
                              onRoute
                                  ? Icons.check_circle
                                  : Icons.location_on_outlined,
                              color: onRoute
                                  ? Colors.green.shade700
                                  : AppTheme.primaryColor,
                            ),
                            title: Text(
                              c.displayName,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text('Cod: ${c.codigoCliente}'),
                            trailing: Text(
                              onRoute ? 'En ruta' : 'Agregar',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: onRoute
                                    ? Colors.green.shade700
                                    : AppTheme.primaryColor,
                              ),
                            ),
                            onTap: () {
                              Navigator.pop(ctx);
                              _toggleClientWithFeedback(c);
                            },
                          );
                        },
                      ),
                    ),
                    ClientListPaginationBar(
                      pagination: pagination,
                      compact: true,
                      onPageChanged: (page) =>
                          setSheetState(() => pagination.goTo(page)),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
    searchController.dispose();
  }

  void _scrollListToClient(String clientId) {
    final index = _filtered.indexWhere((c) => c.id == clientId);
    if (index < 0) return;
    final targetPage = index ~/ kClientListPageSize;
    if (targetPage != _listPagination.page) {
      setState(() => _listPagination.goTo(targetPage));
    }
    final pageIndex = index % kClientListPageSize;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_listScrollController.hasClients) return;
      final offset = (pageIndex * _listCardExtent).clamp(
        0.0,
        _listScrollController.position.maxScrollExtent,
      );
      _listScrollController.animateTo(
        offset,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  Marker _buildClientMarker(ClientModel c, {required bool useGesture}) {
    final onRoute = _selectedIds.contains(c.id);
    final focused = _selectedClient?.id == c.id;
    return Marker(
      key: ValueKey<String>(c.id),
      point: LatLng(c.latitude, c.longitude),
      width: MapClientMarker.hitSize,
      height: MapClientMarker.hitSize,
      child: MapClientMarker(
        client: c,
        onRoute: onRoute,
        focused: focused,
        onTap: useGesture ? () => _onMarkerTap(c) : null,
      ),
    );
  }

  Widget _buildClientMarkersLayer() {
    final markers = _filtered.map((c) => _buildClientMarker(c, useGesture: true)).toList();
    if (_filtered.length >= _clusterMinClients) {
      return MarkerClusterLayerWidget(
        options: MarkerClusterLayerOptions(
          maxClusterRadius: 45,
          size: const Size(MapClientMarker.hitSize, MapClientMarker.hitSize),
          markers: _filtered
              .map((c) => _buildClientMarker(c, useGesture: false))
              .toList(),
          onMarkerTap: _onClusterMarkerTap,
          builder: (context, clusterMarkers) {
            return Container(
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppTheme.primaryColor,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2),
                boxShadow: const [
                  BoxShadow(color: Colors.black26, blurRadius: 4),
                ],
              ),
              child: Text(
                '${clusterMarkers.length}',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                ),
              ),
            );
          },
        ),
      );
    }
    return MarkerLayer(markers: markers);
  }

  void _selectAllVisible() {
    setState(() {
      for (final c in _filtered) {
        _selectedIds.add(c.id);
      }
      _saveMsg = null;
    });
  }

  void _clearSelection() {
    setState(() {
      _selectedIds.clear();
      _saveMsg = null;
    });
  }

  void _selectClientsInVisibleArea() {
    final bounds = _mapController.camera.visibleBounds;
    final inArea = _filtered
        .where((c) => bounds.contains(LatLng(c.latitude, c.longitude)))
        .map((c) => c.id);
    setState(() {
      _selectedIds.addAll(inArea);
      _saveMsg = null;
    });
  }

  void _toggleDrawZoneMode() {
    setState(() {
      _drawingZone = !_drawingZone;
      if (!_drawingZone) {
        _drawnZonePoints.clear();
      }
    });
  }

  void _addZonePoint(LatLng point) {
    if (!_drawingZone) return;
    setState(() => _drawnZonePoints.add(point));
  }

  void _clearDrawnZone() {
    setState(() => _drawnZonePoints.clear());
  }

  void _selectClientsInDrawnZone() {
    if (_drawnZonePoints.length < 3) return;
    final polygon = List<LatLng>.from(_drawnZonePoints);
    final inPolygon = _filtered
        .where((c) => _isInsidePolygon(LatLng(c.latitude, c.longitude), polygon))
        .map((c) => c.id);
    setState(() {
      _selectedIds.addAll(inPolygon);
      _saveMsg = null;
      _drawingZone = false;
      _drawnZonePoints.clear();
    });
  }

  bool _isInsidePolygon(LatLng point, List<LatLng> polygon) {
    var inside = false;
    for (int i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      final xi = polygon[i].longitude;
      final yi = polygon[i].latitude;
      final xj = polygon[j].longitude;
      final yj = polygon[j].latitude;
      final intersects = ((yi > point.latitude) != (yj > point.latitude)) &&
          (point.longitude <
              (xj - xi) * (point.latitude - yi) / ((yj - yi) == 0 ? 1e-12 : (yj - yi)) + xi);
      if (intersects) inside = !inside;
    }
    return inside;
  }

  Future<void> _pickRouteDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _routeDate,
      firstDate: DateTime(DateTime.now().year - 2),
      lastDate: DateTime(DateTime.now().year + 1),
    );
    if (picked == null) return;
    setState(() => _routeDate = picked);
  }

  bool _hasActiveMapFilters() {
    final sectionChanged = _sections.isNotEmpty &&
        _selectedSection != null &&
        _selectedSection != _sections.first['id'];
    final now = DateTime.now();
    final dateChanged = _routeDate.year != now.year ||
        _routeDate.month != now.month ||
        _routeDate.day != now.day;
    return sectionChanged || dateChanged;
  }

  Widget _buildSectionDropdown({ValueChanged<String?>? onChanged}) {
    return DropdownButtonFormField<String>(
      value: _selectedSection,
      decoration: const InputDecoration(
        labelText: 'Zona/sección',
        border: OutlineInputBorder(),
        isDense: true,
      ),
      items: _sections
          .map((s) {
            final id = s['id'] as String;
            final coords = (s['clientes_con_coordenadas'] as num?)?.toInt() ?? 0;
            final label = id == _allMySectionsKey
                ? 'Todas mis secciones ($coords con coordenadas)'
                : '${sectionDisplayLabel(id)} ($coords con coordenadas)';
            return DropdownMenuItem<String>(
              value: id,
              child: Text(label, overflow: TextOverflow.ellipsis),
            );
          })
          .toList(),
      onChanged: onChanged ??
          (v) {
            if (v != null) _loadSectionClients(v);
          },
    );
  }

  Future<void> _showMapFiltersSheet() async {
    await AdaptiveSheet.show(
      context: context,
      title: 'Filtros',
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) {
          return Padding(
            padding: EdgeInsets.fromLTRB(
              16,
              8,
              16,
              MediaQuery.paddingOf(ctx).bottom + 16,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildSectionDropdown(
                  onChanged: (v) async {
                    if (v == null) return;
                    await _loadSectionClients(v);
                    if (ctx.mounted) setSheetState(() {});
                  },
                ),
                const SizedBox(height: 16),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.calendar_today_outlined),
                  title: const Text('Fecha de ruta'),
                  subtitle: Text(_dateFormat.format(_routeDate)),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () async {
                    await _pickRouteDate();
                    if (ctx.mounted) setSheetState(() {});
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _showMapActionsSheet() async {
    await AdaptiveSheet.show(
      context: context,
      title: 'Acciones',
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: EdgeInsets.only(bottom: MediaQuery.paddingOf(ctx).bottom),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  leading: _savingRoute
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.save_outlined),
                  title: Text('Guardar (${_selectedIds.length})'),
                  enabled: !_savingRoute && _selectedIds.isNotEmpty,
                  onTap: !_savingRoute && _selectedIds.isNotEmpty
                      ? () {
                          Navigator.pop(ctx);
                          _saveRoute();
                        }
                      : null,
                ),
                ListTile(
                  leading: const Icon(Icons.select_all),
                  title: const Text('Seleccionar visibles'),
                  enabled: _filtered.isNotEmpty,
                  onTap: _filtered.isEmpty
                      ? null
                      : () {
                          Navigator.pop(ctx);
                          _selectAllVisible();
                        },
                ),
                ListTile(
                  leading: const Icon(Icons.crop_free_outlined),
                  title: const Text('Seleccionar zona mapa'),
                  enabled: _filtered.isNotEmpty,
                  onTap: _filtered.isEmpty
                      ? null
                      : () {
                          Navigator.pop(ctx);
                          _selectClientsInVisibleArea();
                        },
                ),
                ListTile(
                  leading: Icon(_drawingZone ? Icons.close : Icons.gesture),
                  title: Text(_drawingZone ? 'Cancelar dibujo' : 'Dibujar zona'),
                  enabled: _filtered.isNotEmpty,
                  onTap: _filtered.isEmpty
                      ? null
                      : () {
                          Navigator.pop(ctx);
                          _toggleDrawZoneMode();
                        },
                ),
                ListTile(
                  leading: const Icon(Icons.clear_all),
                  title: const Text('Deseleccionar todos'),
                  enabled: _selectedIds.isNotEmpty,
                  onTap: _selectedIds.isEmpty
                      ? null
                      : () {
                          Navigator.pop(ctx);
                          _clearSelection();
                        },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildSearchAndToolbarRow({
    required int withCoords,
    required int total,
  }) {
    final filterIcon = Icon(
      Icons.tune,
      color: _hasActiveMapFilters() ? AppTheme.primaryColor : null,
    );

    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _searchController,
            decoration: const InputDecoration(
              hintText: 'Buscar cliente por nombre o código',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onChanged: _applySearch,
          ),
        ),
        const SizedBox(width: 4),
        IconButton(
          onPressed: _showMapFiltersSheet,
          icon: _hasActiveMapFilters()
              ? Badge(child: filterIcon)
              : filterIcon,
          tooltip: 'Filtros',
        ),
        IconButton(
          onPressed: _showMapActionsSheet,
          icon: const Icon(Icons.more_vert),
          tooltip: 'Acciones',
        ),
        Padding(
          padding: const EdgeInsets.only(left: 4),
          child: Text(
            '$withCoords/$total',
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
          ),
        ),
      ],
    );
  }

  Future<void> _openClientDetail(ClientModel client) async {
    if (_campaignId == null) return;
    final section = client.seccionKey.isNotEmpty
        ? client.seccionKey
        : (_selectedSection != null && _selectedSection != _allMySectionsKey
            ? _selectedSection!
            : (_gestorSectionKeys.isNotEmpty ? _gestorSectionKeys.first : ''));
    if (section.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No se pudo determinar la sección del cliente.')),
      );
      return;
    }

    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => ClientDetailScreen(
          client: client,
          campaignId: _campaignId!,
          section: section,
        ),
      ),
    );

    if (result == true && mounted && _selectedSection != null) {
      await _loadSectionClients(_selectedSection!);
    }
  }

  Future<void> _saveRoute() async {
    if (_selectedIds.isEmpty) return;
    final auth = context.read<AuthService>();
    final profile = auth.profile;
    final user = auth.firebaseUser;
    if (user == null) return;

    final selected = _clients.where((c) => _selectedIds.contains(c.id)).toList();
    if (selected.isEmpty) return;

    setState(() {
      _savingRoute = true;
      _saveMsg = null;
    });

    final docId = await _firestoreService.saveMyRoute(
      fecha: _dateFormat.format(_routeDate),
      gestorNombre: profile?.nombre.isNotEmpty == true
          ? profile!.nombre
          : (user.email ?? 'Gestor'),
      clientes: selected,
    );

    if (!mounted) return;
    setState(() {
      _savingRoute = false;
      _saveMsg = docId == null
          ? 'No se pudo guardar la ruta. Intenta nuevamente.'
          : 'Ruta guardada con ${selected.length} clientes';
    });

    if (docId != null) {
      context.read<RouteRefreshService>().notifyRoutesChanged();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Ruta guardada (${selected.length} clientes). Revisa en Mis rutas.'),
          duration: const Duration(seconds: 4),
        ),
      );
    }
  }

  void _fitToMarkers() {
    if (_filtered.isEmpty && _myPosition == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final points = _filtered
          .map((c) => LatLng(c.latitude, c.longitude))
          .toList();
      if (_myPosition != null) points.add(_myPosition!);
      if (points.isEmpty) return;
      try {
        if (points.length == 1) {
          _mapController.move(points.first, 15);
          return;
        }
        final lats = points.map((p) => p.latitude);
        final lngs = points.map((p) => p.longitude);
        _mapController.fitCamera(
          CameraFit.bounds(
            bounds: LatLngBounds(
              LatLng(lats.reduce((a, b) => a < b ? a : b),
                  lngs.reduce((a, b) => a < b ? a : b)),
              LatLng(lats.reduce((a, b) => a > b ? a : b),
                  lngs.reduce((a, b) => a > b ? a : b)),
            ),
            padding: const EdgeInsets.all(48),
          ),
        );
      } catch (_) {
        refreshMapTiles(_mapController);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final campanaFilterNotifier = context.watch<CampanaBancoFilterNotifier>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mapa de Clientes'),
        actions: [
          PopupMenuButton<int>(
            tooltip: 'Proveedor de mapa',
            onSelected: _selectTileProvider,
            itemBuilder: (_) => MapTilesConfig.buildSourceMenuItems(),
            icon: const Icon(Icons.layers_outlined, color: Colors.white),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: () {
              _mapDataLoadStarted = true;
              _awaitingTabActivation = false;
              _loadInitial();
            },
          ),
        ],
      ),
      body: _awaitingTabActivation
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  'Abre la pestaña Mapa para cargar los clientes.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey.shade700, fontSize: 14),
                ),
              ),
            )
          : _loading
              ? const Center(
                  child: CircularProgressIndicator(color: AppTheme.primaryColor),
                )
              : _campaignId == null
                  ? const Center(child: Text('No hay campaña activa'))
                  : Column(
                      children: [
                        _buildTopControls(campanaFilterNotifier),
                        Expanded(child: _buildMapLayout()),
                      ],
                    ),
    );
  }

  Widget _buildMapLayout() {
    if (context.isExpanded) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(flex: 2, child: _buildMap()),
          const VerticalDivider(width: 1),
          Expanded(flex: 1, child: _buildSideClientList()),
        ],
      );
    }
    return Column(
      children: [
        Expanded(child: _buildMap()),
        _buildBottomList(),
      ],
    );
  }

  Widget _buildSideClientList() {
    final pageClients = _listPagination.slice(_filtered);
    return ColoredBox(
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
            child: Text(
              '${_filtered.length} clientes con coordenadas',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
          ),
          Expanded(
            child: _filtered.isEmpty
                ? Center(
                    child: Text(
                      'Sin clientes en esta sección',
                      style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                    ),
                  )
                : ListView.builder(
                    itemCount: pageClients.length,
                    itemBuilder: (context, i) {
                      final c = pageClients[i];
                      final selected = _selectedClient?.id == c.id;
                      final onRoute = _selectedIds.contains(c.id);
                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                          side: BorderSide(
                            color: onRoute
                                ? Colors.green.shade700
                                : (selected
                                    ? AppTheme.primaryColor
                                    : Colors.grey.shade200),
                            width: selected || onRoute ? 2 : 1,
                          ),
                        ),
                        child: InkWell(
                          onTap: () => _openClientDetail(c),
                          onLongPress: () {
                            setState(() => _selectedClient = c);
                            _focusClientOnMap(c);
                          },
                          mouseCursor: SystemMouseCursors.click,
                          child: Padding(
                            padding: const EdgeInsets.all(10),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  c.displayName,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 13,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Cod: ${c.codigoCliente}',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: Colors.grey.shade600,
                                  ),
                                ),
                                if (c.direccion.isNotEmpty) ...[
                                  const SizedBox(height: 4),
                                  Text(
                                    c.direccion,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.grey.shade700,
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    Text(
                                      'S/ ${c.importeDeudaAsignada.toStringAsFixed(0)}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        fontSize: 12,
                                      ),
                                    ),
                                    const Spacer(),
                                    IconButton(
                                      onPressed: () => _toggleClientWithFeedback(c),
                                      icon: Icon(
                                        onRoute
                                            ? Icons.check_circle
                                            : Icons.add_circle_outline,
                                        color: onRoute
                                            ? Colors.green.shade700
                                            : Colors.grey.shade600,
                                      ),
                                      tooltip: onRoute
                                          ? 'Quitar de ruta'
                                          : 'Agregar a ruta',
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          ClientListPaginationBar(
            pagination: _listPagination,
            compact: true,
            onPageChanged: (page) => setState(() => _listPagination.goTo(page)),
          ),
        ],
      ),
    );
  }

  Widget _buildTopControls(CampanaBancoFilterNotifier campanaFilterNotifier) {
    final selectedMeta = _sections.firstWhere(
      (s) => s['id'] == _selectedSection,
      orElse: () => const {'num_clientes': 0, 'clientes_con_coordenadas': 0},
    );
    final total = (selectedMeta['num_clientes'] as num?)?.toInt() ?? 0;
    final withCoords = (selectedMeta['clientes_con_coordenadas'] as num?)?.toInt() ?? 0;

    return Container(
      padding: const EdgeInsets.all(12),
      color: Colors.white,
      child: Column(
        children: [
          _buildSearchAndToolbarRow(withCoords: withCoords, total: total),
          CampanaBancoFilterBar(
            available: campanaFilterNotifier.available,
            selected: campanaFilterNotifier.selected,
            onSelected: campanaFilterNotifier.select,
          ),
          if (_showMapTapHint) ...[
            const SizedBox(height: 8),
            Material(
              color: Colors.indigo.shade50,
              borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.touch_app_outlined,
                        size: 18, color: Colors.indigo.shade800),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Toca un punto del mapa para agregarlo o quitarlo de tu ruta.',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.indigo.shade900,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: _dismissMapTapHint,
                      icon: const Icon(Icons.close, size: 18),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      tooltip: 'Cerrar',
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (_drawingZone) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(
                  child: Text(
                    _drawnZonePoints.length < 3
                        ? 'Toca el mapa para marcar al menos 3 puntos.'
                        : 'Zona lista. Puedes seleccionar clientes dentro.',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                  ),
                ),
                TextButton(
                  onPressed: _drawnZonePoints.isEmpty ? null : _clearDrawnZone,
                  child: const Text('Borrar puntos'),
                ),
                const SizedBox(width: 4),
                ElevatedButton(
                  onPressed: _drawnZonePoints.length < 3 ? null : _selectClientsInDrawnZone,
                  child: const Text('Seleccionar zona'),
                ),
              ],
            ),
          ],
          if (_saveMsg != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                _saveMsg!,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: _saveMsg!.startsWith('Ruta guardada')
                      ? Colors.green.shade700
                      : Colors.red.shade700,
                ),
              ),
            ),
          if (_positionHint != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                _positionHint!,
                style: TextStyle(fontSize: 12, color: Colors.orange.shade800),
              ),
            ),
          if (_loadError != null) _buildLoadErrorBanner(),
        ],
      ),
    );
  }

  Widget _buildMapLegend() {
    return Positioned(
      left: 8,
      bottom: 8,
      child: Material(
        elevation: 2,
        borderRadius: BorderRadius.circular(8),
        color: Colors.white.withValues(alpha: 0.95),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _legendRow(Colors.green.shade700, 'En mi ruta'),
              const SizedBox(height: 4),
              _legendRow(AppTheme.primaryColor, 'Disponible'),
              const SizedBox(height: 4),
              _legendRow(Colors.amber.shade600, 'Último tocado', ring: true),
            ],
          ),
        ),
      ),
    );
  }

  Widget _legendRow(Color color, String label, {bool ring = false}) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: ring ? Colors.transparent : color,
            border: ring ? Border.all(color: color, width: 2) : null,
          ),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.black87)),
      ],
    );
  }

  Widget _buildTileErrorChip() {
    final count = MapTilesConfig.tileErrorCount.value;
    return Positioned(
      top: 8,
      right: 8,
      left: 8,
      child: Material(
        elevation: 3,
        borderRadius: BorderRadius.circular(8),
        color: Colors.orange.shade50,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: Row(
            children: [
              Icon(Icons.map_outlined, size: 18, color: Colors.orange.shade900),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Mapa: $count tile${count == 1 ? '' : 's'} no cargado${count == 1 ? '' : 's'}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.orange.shade900,
                  ),
                ),
              ),
              TextButton(
                onPressed: _cycleTileProvider,
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: const Text('Cambiar proveedor'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoadErrorBanner() {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Material(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.error_outline, size: 18, color: Colors.red.shade700),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _loadError!,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.red.shade700,
                  ),
                ),
              ),
              TextButton(
                onPressed: _loading || _loadingClients
                    ? null
                    : () {
                        if (_selectedSection != null) {
                          _loadSectionClients(_selectedSection!);
                        } else {
                          _loadInitial();
                        }
                      },
                child: const Text('Reintentar'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMap() {
    final defaultCenter = _myPosition ?? const LatLng(-12.0464, -77.0428);
    final center = _filtered.isNotEmpty
        ? LatLng(_filtered.first.latitude, _filtered.first.longitude)
        : defaultCenter;
    final mapKey = ValueKey('client-map-$_tileSourceIndex');

    return Stack(
      children: [
        FlutterMap(
          key: mapKey,
          mapController: _mapController,
          options: MapOptions(
            initialCenter: center,
            initialZoom: _filtered.isEmpty ? 13 : 12,
            minZoom: 4,
            maxZoom: 19,
            interactionOptions: const InteractionOptions(
              flags: InteractiveFlag.all,
            ),
            onTap: (_, point) => _addZonePoint(point),
            onMapReady: () {
              if (_filtered.isNotEmpty) {
                _fitToMarkers();
              }
            },
          ),
          children: [
            MapTilesConfig.buildTileLayer(
              sourceIndex: _tileSourceIndex,
              key: ValueKey('tiles-$_tileSourceIndex-$mapMountGeneration'),
            ),
            if (_drawnZonePoints.isNotEmpty)
              PolygonLayer(
                polygons: <Polygon>[
                  Polygon(
                    points: _drawnZonePoints,
                    color: AppTheme.primaryColor.withValues(alpha: 0.18),
                    borderColor: AppTheme.primaryColor,
                    borderStrokeWidth: 2,
                  ),
                ],
              ),
            if (_drawnZonePoints.isNotEmpty)
              PolylineLayer(
                polylines: [
                  Polyline(
                    points: _drawnZonePoints,
                    strokeWidth: 2,
                    color: AppTheme.primaryColor,
                  ),
                ],
              ),
            if (_myPosition != null)
              MarkerLayer(
                markers: [
                  Marker(
                    point: _myPosition!,
                    width: 34,
                    height: 34,
                    child: Container(
                      decoration: BoxDecoration(
                        color: Colors.blue.shade700,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2),
                        boxShadow: const [
                          BoxShadow(color: Colors.black26, blurRadius: 4),
                        ],
                      ),
                      child: const Icon(
                        Icons.person_pin_circle,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ),
                ],
              ),
            IgnorePointer(
              ignoring: _drawingZone,
              child: _buildClientMarkersLayer(),
            ),
            MapTilesConfig.buildAttribution(_tileSourceIndex),
          ],
        ),
        if (MapTilesConfig.tileErrorCount.value > 0) _buildTileErrorChip(),
        if (_filtered.isNotEmpty) _buildMapLegend(),
        if (_selectedIds.isNotEmpty)
          Positioned(
            top: 8,
            right: 8,
            child: Material(
              elevation: 2,
              borderRadius: BorderRadius.circular(20),
              color: Colors.green.shade700,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                child: Text(
                  'En ruta: ${_selectedIds.length}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ),
        if (_loadingClients)
          const Positioned.fill(
            child: IgnorePointer(
              child: ColoredBox(
              color: Color(0x66FFFFFF),
              child: Center(child: CircularProgressIndicator()),
            ),
            ),
          ),
        if (!_loadingClients && _filtered.isEmpty)
          Positioned(
            left: 12,
            right: 12,
            top: 12,
            child: Material(
              elevation: 2,
              borderRadius: BorderRadius.circular(8),
              color: Colors.white,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _sections.isEmpty
                      ? 'No tienes secciones asignadas. Contacta al administrador.'
                      : 'Sin clientes con coordenadas en esta sección. '
                          'Las visitas con GPS también aparecen aquí.',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade800),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildBottomList() {
    final pageClients = _listPagination.slice(_filtered);
    return ColoredBox(
      color: Colors.white,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            height: 120,
            child: _filtered.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Text(
                        _sections.isEmpty
                            ? 'Sin secciones asignadas'
                            : 'Sin clientes con coordenadas en esta sección',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            color: Colors.grey.shade600, fontSize: 13),
                      ),
                    ),
                  )
                : ListView.builder(
                    controller: _listScrollController,
                    itemCount: pageClients.length,
                    scrollDirection: Axis.horizontal,
                    itemBuilder: (context, i) {
                      final c = pageClients[i];
                final selected = _selectedClient?.id == c.id;
                final onRoute = _selectedIds.contains(c.id);
                return GestureDetector(
                  onTap: () => _openClientDetail(c),
                  onLongPress: () {
                    setState(() => _selectedClient = c);
                    _focusClientOnMap(c);
                    _scrollListToClient(c.id);
                  },
                  child: Container(
                    width: 180,
                    margin: const EdgeInsets.all(8),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: onRoute
                            ? Colors.green.shade700
                            : (selected ? AppTheme.primaryColor : Colors.grey.shade300),
                        width: selected ? 2 : 1,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(c.displayName,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
                        const SizedBox(height: 6),
                        Text('Cod: ${c.codigoCliente}',
                            style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                        const Spacer(),
                        Row(
                          children: [
                            Expanded(
                              child: TextButton.icon(
                                onPressed: () => _openInGoogleMaps(c.latitude, c.longitude),
                                style: TextButton.styleFrom(
                                  padding: EdgeInsets.zero,
                                  minimumSize: const Size(0, 0),
                                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                                icon: const Icon(Icons.map, size: 14),
                                label: const Text('Maps', style: TextStyle(fontSize: 11)),
                              ),
                            ),
                            TextButton.icon(
                              onPressed: () => _openClientDetail(c),
                              style: TextButton.styleFrom(
                                padding: EdgeInsets.zero,
                                minimumSize: const Size(0, 0),
                                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                              ),
                              icon: const Icon(Icons.person_outline, size: 14),
                              label: const Text('Ficha', style: TextStyle(fontSize: 11)),
                            ),
                            IconButton(
                              onPressed: () => _toggleClientWithFeedback(c),
                              iconSize: 18,
                              visualDensity: VisualDensity.compact,
                              icon: Icon(
                                onRoute
                                    ? Icons.check_circle
                                    : Icons.add_circle_outline,
                                color: onRoute ? Colors.green.shade700 : Colors.grey.shade600,
                              ),
                              tooltip: onRoute ? 'Quitar de ruta' : 'Agregar a ruta',
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          ClientListPaginationBar(
            pagination: _listPagination,
            compact: true,
            onPageChanged: (page) => setState(() {
              _listPagination.goTo(page);
              if (_listScrollController.hasClients) {
                _listScrollController.jumpTo(0);
              }
            }),
          ),
        ],
      ),
    );
  }

  Future<void> _openInGoogleMaps(double lat, double lng) async {
    final uri = Uri.parse('https://www.google.com/maps?q=$lat,$lng');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}
