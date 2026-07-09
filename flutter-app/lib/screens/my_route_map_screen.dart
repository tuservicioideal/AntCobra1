import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/map_tiles.dart';
import '../config/theme.dart';
import '../services/connectivity_service.dart';
import '../services/location_service.dart';
import '../services/road_routing_service.dart';
import '../utils/google_maps_route_url.dart';
import '../utils/client_list_pagination.dart';
import '../utils/responsive.dart';
import '../utils/route_ordering.dart';
import '../widgets/client_list_pagination_bar.dart';

class MyRouteMapScreen extends StatefulWidget {
  const MyRouteMapScreen({
    super.key,
    required this.route,
  });

  final Map<String, dynamic> route;

  @override
  State<MyRouteMapScreen> createState() => _MyRouteMapScreenState();
}

class _MyRouteMapScreenState extends State<MyRouteMapScreen> {
  final _locationService = LocationService();
  final _routingService = RoadRoutingService();
  final _mapController = MapController();
  final _searchController = TextEditingController();
  final _pagination = ClientListPagination();

  bool _loading = true;
  bool _routingLoading = false;
  String? _error;
  String? _routingBanner;
  LatLng? _myPosition;
  List<Map<String, dynamic>> _orderedClients = [];
  List<LatLng> _roadPoints = [];
  bool _routingFailed = false;
  int _tileSourceIndex = 0;

  @override
  void initState() {
    super.initState();
    _prepareRoute();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _routingService.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> get _filteredClients {
    final q = _searchController.text.trim();
    if (q.isEmpty) return _orderedClients;
    return _orderedClients
        .where((c) => matchesRouteClientMap(c, q))
        .toList();
  }

  List<LatLng> get _straightPolylinePoints => [
        if (_myPosition != null) _myPosition!,
        ...clientMapsToLatLng(_orderedClients),
      ];

  List<LatLng> get _displayPolylinePoints =>
      _roadPoints.length >= 2 ? _roadPoints : _straightPolylinePoints;

  Future<void> _prepareRoute() async {
    setState(() {
      _loading = true;
      _error = null;
      _routingBanner = null;
      _roadPoints = [];
      _routingFailed = false;
      _pagination.reset();
      _searchController.clear();
    });

    try {
      await _locationService.getCurrentPosition();
      final myLat = _locationService.latitude;
      final myLng = _locationService.longitude;
      if (myLat != null && myLng != null) {
        _myPosition = LatLng(myLat, myLng);
      }

      final clients = parseRouteClients(widget.route['clientes'] as List?);

      if (clients.isEmpty) {
        setState(() {
          _error = 'No hay clientes con coordenadas para esta ruta.';
          _loading = false;
        });
        return;
      }

      _orderedClients = orderClientsByNearest(clients, _myPosition);
    } catch (_) {
      _error = 'No se pudo preparar el mapa de la ruta.';
    }

    if (!mounted) return;
    setState(() => _loading = false);

    if (_error == null && _orderedClients.isNotEmpty) {
      await _fetchRoadRoute();
    }
  }

  Future<void> _fetchRoadRoute() async {
    final waypoints = _straightPolylinePoints;
    if (waypoints.length < 2) return;

    final online = context.read<ConnectivityService>().isOnline;
    if (!online) {
      if (!mounted) return;
      setState(() {
        _routingFailed = true;
        _routingBanner = 'Sin conexión: ruta en línea recta';
      });
      return;
    }

    setState(() {
      _routingLoading = true;
      _routingBanner = 'Calculando ruta por carretera…';
    });

    try {
      final result = await _routingService.fetchRoute(waypoints);
      if (!mounted) return;
      setState(() {
        _roadPoints = result.points;
        _routingFailed = false;
        _routingBanner =
            '~${result.distanceKm.toStringAsFixed(1)} km · ~${result.durationMinutes.round()} min (carretera)';
      });
      _fitMapToRoute(result.points);
    } on RoadRoutingException catch (e) {
      if (!mounted) return;
      setState(() {
        _routingFailed = true;
        _routingBanner = 'Ruta aproximada (línea recta): ${e.message}';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _routingFailed = true;
        _routingBanner = 'Ruta aproximada (línea recta)';
      });
    } finally {
      if (mounted) {
        setState(() => _routingLoading = false);
      }
    }
  }

  void _fitMapToRoute(List<LatLng> points) {
    if (points.length < 2) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      try {
        final lats = points.map((p) => p.latitude);
        final lngs = points.map((p) => p.longitude);
        _mapController.fitCamera(
          CameraFit.bounds(
            bounds: LatLngBounds(
              LatLng(
                lats.reduce((a, b) => a < b ? a : b),
                lngs.reduce((a, b) => a < b ? a : b),
              ),
              LatLng(
                lats.reduce((a, b) => a > b ? a : b),
                lngs.reduce((a, b) => a > b ? a : b),
              ),
            ),
            padding: const EdgeInsets.all(48),
          ),
        );
      } catch (_) {
        refreshMapTiles(_mapController);
      }
    });
  }

  Future<void> _openFullRouteInGoogleMaps() async {
    final clientStops = clientMapsToLatLng(_orderedClients);
    if (clientStops.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No hay paradas con coordenadas.')),
      );
      return;
    }

    try {
      final built = buildGoogleMapsDrivingUrl(
        clientStops: clientStops,
        origin: _myPosition,
      );
      final launched = await launchUrl(
        built.uri,
        mode: LaunchMode.externalApplication,
      );
      if (!mounted) return;
      if (!launched) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No se pudo abrir Google Maps.')),
        );
        return;
      }
      if (built.wasTruncated) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Google Maps admite hasta ${kGoogleMapsMaxWaypoints + 2} paradas. '
              'Se exportaron ${built.exportedStopCount} de ${built.totalStopCount}.',
            ),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al abrir Google Maps: $e')),
      );
    }
  }

  Future<void> _openDirectionsTo(Map<String, dynamic> client) async {
    final lat = (client['lat'] as num).toDouble();
    final lng = (client['lng'] as num).toDouble();
    final uri = Uri.parse(
      'https://www.google.com/maps/dir/?api=1&destination=$lat,$lng&travelmode=driving',
    );
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  String _routeTitle() {
    final nombre = widget.route['nombre']?.toString().trim() ?? '';
    if (nombre.isNotEmpty) return nombre;
    final fecha = widget.route['fecha']?.toString() ?? '';
    if (fecha.isEmpty) return 'Ruta en mapa';
    try {
      return DateFormat('dd/MM/yyyy').format(DateFormat('yyyy-MM-dd').parse(fecha));
    } catch (_) {
      return fecha;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator(color: AppTheme.primaryColor)),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: Text(_routeTitle())),
        body: Center(child: Text(_error!)),
      );
    }

    final markers = <Marker>[
      if (_myPosition != null)
        Marker(
          point: _myPosition!,
          width: 20,
          height: 20,
          child: const Icon(Icons.my_location, color: Colors.blue, size: 20),
        ),
      ..._orderedClients.asMap().entries.map((entry) {
        final idx = entry.key + 1;
        final c = entry.value;
        final point = LatLng((c['lat'] as num).toDouble(), (c['lng'] as num).toDouble());
        return Marker(
          point: point,
          width: 34,
          height: 34,
          child: CircleAvatar(
            radius: 17,
            backgroundColor: Colors.red.shade600,
            child: Text(
              '$idx',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
            ),
          ),
        );
      }),
    ];

    final firstPoint = _displayPolylinePoints.first;
    final polylineColor = _routingFailed
        ? Colors.orange.shade700
        : AppTheme.primaryColor;

    return Scaffold(
      appBar: AppBar(
        title: Text(_routeTitle()),
        actions: [
          IconButton(
            tooltip: 'Abrir ruta en Google Maps',
            onPressed: _openFullRouteInGoogleMaps,
            icon: const Icon(Icons.map_outlined, color: Colors.white),
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
        ],
      ),
      body: Column(
        children: [
          if (_routingBanner != null || _routingLoading)
            Material(
              color: _routingFailed ? Colors.amber.shade50 : Colors.blue.shade50,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    if (_routingLoading)
                      const Padding(
                        padding: EdgeInsets.only(right: 8),
                        child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      ),
                    Expanded(
                      child: Text(
                        _routingBanner ?? '',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: _routingFailed
                              ? Colors.amber.shade900
                              : Colors.blue.shade900,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          Expanded(child: _buildRouteLayout(markers, firstPoint, polylineColor)),
        ],
      ),
    );
  }

  Widget _buildRouteClientList() {
    final filtered = _filteredClients;
    final pageItems = _pagination.slice(filtered);

    return ColoredBox(
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Buscar cliente en la ruta…',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _pagination.reset());
                        },
                      )
                    : null,
                isDense: true,
                border: const OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() => _pagination.reset()),
            ),
          ),
          Expanded(
            child: pageItems.isEmpty
                ? Center(
                    child: Text(
                      _searchController.text.isNotEmpty
                          ? 'Sin coincidencias'
                          : 'Sin clientes',
                      style: TextStyle(color: Colors.grey.shade600),
                    ),
                  )
                : ListView.builder(
                    itemCount: pageItems.length,
                    itemBuilder: (_, i) {
                      final c = pageItems[i];
                      final globalIndex = _orderedClients.indexOf(c);
                      final order = globalIndex >= 0 ? globalIndex + 1 : i + 1;
                      final name = c['nombre']?.toString() ?? 'Cliente';
                      return ListTile(
                        leading: CircleAvatar(
                          radius: 14,
                          backgroundColor: AppTheme.primaryColor,
                          child: Text(
                            '$order',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                            ),
                          ),
                        ),
                        title: Text(name),
                        subtitle: Text(c['codigo_cliente']?.toString() ?? '—'),
                        trailing: IconButton(
                          icon: const Icon(Icons.navigation_outlined),
                          tooltip: 'Abrir en Google Maps',
                          onPressed: () => _openDirectionsTo(c),
                        ),
                      );
                    },
                  ),
          ),
          ClientListPaginationBar(
            pagination: _pagination,
            compact: true,
            onPageChanged: (page) => setState(() => _pagination.goTo(page)),
          ),
        ],
      ),
    );
  }

  Widget _buildRouteMap(
    List<Marker> markers,
    LatLng firstPoint,
    Color polylineColor,
  ) {
    return FlutterMap(
      mapController: _mapController,
      options: MapOptions(
        initialCenter: firstPoint,
        initialZoom: 13,
        minZoom: 4,
        maxZoom: 19,
        onMapReady: () => refreshMapTiles(_mapController),
      ),
      children: [
        MapTilesConfig.buildTileLayer(sourceIndex: _tileSourceIndex),
        PolylineLayer(
          polylines: [
            Polyline(
              points: _displayPolylinePoints,
              strokeWidth: 4,
              color: polylineColor,
            ),
          ],
        ),
        MarkerLayer(markers: markers),
        MapTilesConfig.buildAttribution(_tileSourceIndex),
      ],
    );
  }

  Widget _buildRouteLayout(
    List<Marker> markers,
    LatLng firstPoint,
    Color polylineColor,
  ) {
    if (context.isExpanded) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            flex: 2,
            child: _buildRouteMap(markers, firstPoint, polylineColor),
          ),
          const VerticalDivider(width: 1),
          Expanded(flex: 1, child: _buildRouteClientList()),
        ],
      );
    }

    return Column(
      children: [
        Expanded(child: _buildRouteMap(markers, firstPoint, polylineColor)),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: 'Buscar cliente en la ruta…',
              prefixIcon: const Icon(Icons.search, size: 20),
              suffixIcon: _searchController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, size: 18),
                      onPressed: () {
                        _searchController.clear();
                        setState(() => _pagination.reset());
                      },
                    )
                  : null,
              isDense: true,
              border: const OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() => _pagination.reset()),
          ),
        ),
        Builder(
          builder: (context) {
            final filtered = _filteredClients;
            final pageItems = _pagination.slice(filtered);
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  height: 170,
                  child: pageItems.isEmpty
                      ? Center(
                          child: Text(
                            _searchController.text.isNotEmpty
                                ? 'Sin coincidencias'
                                : 'Sin clientes',
                            style: TextStyle(color: Colors.grey.shade600),
                          ),
                        )
                      : ListView.builder(
                          itemCount: pageItems.length,
                          itemBuilder: (_, i) {
                            final c = pageItems[i];
                            final globalIndex = _orderedClients.indexOf(c);
                            final order =
                                globalIndex >= 0 ? globalIndex + 1 : i + 1;
                            final name = c['nombre']?.toString() ?? 'Cliente';
                            return ListTile(
                              leading: CircleAvatar(
                                radius: 14,
                                backgroundColor: AppTheme.primaryColor,
                                child: Text(
                                  '$order',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                              title: Text(name),
                              subtitle:
                                  Text(c['codigo_cliente']?.toString() ?? '—'),
                              trailing: IconButton(
                                icon: const Icon(Icons.navigation_outlined),
                                onPressed: () => _openDirectionsTo(c),
                              ),
                            );
                          },
                        ),
                ),
                ClientListPaginationBar(
                  pagination: _pagination,
                  compact: true,
                  onPageChanged: (page) =>
                      setState(() => _pagination.goTo(page)),
                ),
              ],
            );
          },
        ),
      ],
    );
  }
}
