import 'package:flutter/material.dart';

import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:intl/intl.dart';

import 'package:provider/provider.dart';

import 'package:url_launcher/url_launcher.dart';

import '../config/theme.dart';

import '../services/location_service.dart';

import '../services/firestore_service.dart';

import '../services/campaign_service.dart';

import '../services/route_refresh_service.dart';

import '../utils/google_maps_route_url.dart';
import '../utils/client_list_pagination.dart';
import '../utils/route_ordering.dart';
import '../widgets/client_list_pagination_bar.dart';
import 'client_detail_screen.dart';
import 'my_route_map_screen.dart';



class MyRoutesScreen extends StatefulWidget {

  const MyRoutesScreen({super.key});



  @override

  State<MyRoutesScreen> createState() => MyRoutesScreenState();

}



class MyRoutesScreenState extends State<MyRoutesScreen> {

  final _firestoreService = FirestoreService();

  final _campaignService = CampaignService();

  final _locationService = LocationService();

  final DateFormat _dateFmt = DateFormat('yyyy-MM-dd');

  final DateFormat _prettyFmt = DateFormat('dd/MM/yyyy');



  List<Map<String, dynamic>> _routes = [];

  bool _loading = true;

  bool _loadingDate = false;

  String? _error;

  String? _warning;

  RouteRefreshService? _refreshService;

  final _searchController = TextEditingController();

  String _searchQuery = '';

  final _searchPagination = ClientListPagination();

  final Map<String, int> _routeClientPages = {};

  @override

  void initState() {

    super.initState();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _loadRoutes();
    });

  }

  @override

  void didChangeDependencies() {

    super.didChangeDependencies();

    final next = context.read<RouteRefreshService>();

    if (!identical(_refreshService, next)) {

      _refreshService?.removeListener(_onRefreshSignal);

      _refreshService = next;

      _refreshService?.addListener(_onRefreshSignal);

    }

  }

  @override

  void dispose() {

    _refreshService?.removeListener(_onRefreshSignal);

    _searchController.dispose();

    super.dispose();

  }



  void _onRefreshSignal() {

    if (mounted) reload();

  }



  void reload() => _loadRoutes();



  Future<void> _loadRoutes() async {

    setState(() {

      _loading = true;

      _error = null;

      _warning = null;

    });

    try {

      final result = await _firestoreService.getMyRoutes(limit: 45);

      if (!mounted) return;

      setState(() {

        _routes = result.routes;

        _error = result.hasError ? result.error : null;

        _warning = result.warning;

      });

    } catch (e) {

      if (!mounted) return;

      setState(() {

        _routes = [];

        _error = 'No se pudo cargar Mis rutas.';

      });

    } finally {

      if (mounted) {

        setState(() => _loading = false);

      }

    }

  }



  Future<void> _pickDateAndLoad() async {

    final now = DateTime.now();

    final picked = await showDatePicker(

      context: context,

      initialDate: now,

      firstDate: DateTime(now.year - 2),

      lastDate: DateTime(now.year + 1),

    );

    if (picked == null) return;



    setState(() {

      _loadingDate = true;

      _error = null;

    });

    final key = _dateFmt.format(picked);

    final route = await _firestoreService.getMyRouteByDate(key);

    if (!mounted) return;

    setState(() {

      _loadingDate = false;

      if (route == null) {

        _error = 'No hay ruta guardada para ${_prettyFmt.format(picked)}.';

      } else {

        _routes = [route, ..._routes.where((r) => (r['id'] ?? '') != (route['id'] ?? ''))];

        _error = null;

      }

    });

  }



  String _prettyDate(String? raw) {

    if (raw == null || raw.isEmpty) return 'Sin fecha';

    try {

      final parsed = DateFormat('yyyy-MM-dd').parse(raw);

      return _prettyFmt.format(parsed);

    } catch (_) {

      return raw;

    }

  }

  String _routeDisplayTitle(Map<String, dynamic> route) {
    final nombre = route['nombre']?.toString().trim() ?? '';
    if (nombre.isNotEmpty) return nombre;
    return _prettyDate(route['fecha']?.toString());
  }

  String _routeDisplaySubtitle(Map<String, dynamic> route) {
    final nombre = route['nombre']?.toString().trim() ?? '';
    final fecha = route['fecha']?.toString() ?? '';
    final clientes = (route['clientes'] as List?) ?? const [];
    final total = (route['total'] as num?)?.toInt() ?? clientes.length;
    final completados = (route['completados'] as num?)?.toInt() ?? 0;
    final counts = '$total clientes · $completados completados';
    if (nombre.isNotEmpty && fecha.isNotEmpty) {
      return '${_prettyDate(fecha)} · $counts';
    }
    return counts;
  }

  Future<void> _renameRoute(Map<String, dynamic> route) async {
    final docId = route['id']?.toString();
    if (docId == null || docId.isEmpty) return;

    final controller = TextEditingController(
      text: route['nombre']?.toString() ?? '',
    );

    final newName = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cambiar nombre de ruta'),
        content: TextField(
          controller: controller,
          decoration: InputDecoration(
            labelText: 'Nombre',
            hintText: _prettyDate(route['fecha']?.toString()),
          ),
          autofocus: true,
          maxLength: 80,
          textCapitalization: TextCapitalization.sentences,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );

    controller.dispose();
    if (newName == null || !mounted) return;

    final ok = await _firestoreService.updateMyRouteName(
      docId: docId,
      nombre: newName,
    );
    if (!mounted) return;

    if (!ok) {
      setState(() => _error = 'No se pudo actualizar el nombre de la ruta.');
      return;
    }

    setState(() {
      _error = null;
      final idx = _routes.indexWhere((r) => r['id'] == docId);
      if (idx >= 0) {
        if (newName.isEmpty) {
          _routes[idx].remove('nombre');
        } else {
          _routes[idx]['nombre'] = newName;
        }
      }
    });

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          newName.isEmpty
              ? 'Nombre restablecido a la fecha.'
              : 'Ruta renombrada correctamente.',
        ),
      ),
    );
  }

  Future<void> _deleteRoute(Map<String, dynamic> route) async {
    final docId = route['id']?.toString();
    if (docId == null || docId.isEmpty) return;

    final display = _routeDisplayTitle(route);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Eliminar ruta'),
        content: Text(
          '¿Eliminar la ruta "$display"? Esta acción no se puede deshacer.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    final ok = await _firestoreService.deleteMyRoute(docId);
    if (!mounted) return;

    if (!ok) {
      setState(() => _error = 'No se pudo eliminar la ruta.');
      return;
    }

    setState(() {
      _error = null;
      _routes.removeWhere((r) => r['id'] == docId);
      _routeClientPages.remove(docId);
    });

    context.read<RouteRefreshService>().notifyRoutesChanged();

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Ruta eliminada.')),
    );
  }

  void _onRouteMenuSelected(String action, Map<String, dynamic> route) {
    switch (action) {
      case 'rename':
        _renameRoute(route);
        break;
      case 'delete':
        _deleteRoute(route);
        break;
    }
  }

  Widget _buildRouteMenu(Map<String, dynamic> route) {
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert),
      tooltip: 'Opciones de ruta',
      onSelected: (action) => _onRouteMenuSelected(action, route),
      itemBuilder: (context) => [
        const PopupMenuItem(
          value: 'rename',
          child: ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.edit_outlined, size: 20),
            title: Text('Cambiar nombre'),
          ),
        ),
        PopupMenuItem(
          value: 'delete',
          child: ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.delete_outline, size: 20, color: Colors.red.shade700),
            title: Text(
              'Eliminar ruta',
              style: TextStyle(color: Colors.red.shade700),
            ),
          ),
        ),
      ],
    );
  }



  Future<void> _openClientFromRoute(Map<String, dynamic> routeClient) async {
    final clientId = routeClient['codigo_cliente']?.toString() ?? '';
    final section = routeClient['seccion_key']?.toString() ?? '';
    if (clientId.isEmpty || section.isEmpty) {
      if (!mounted) return;
      setState(() => _error = 'Datos incompletos del cliente en la ruta.');
      return;
    }

    final campaignId = await _campaignService.getActiveCampaignId();
    if (!mounted) return;
    if (campaignId == null) {
      setState(() => _error = 'No hay campaña activa.');
      return;
    }

    final client = await _firestoreService.getClient(
      campaignId: campaignId,
      section: section,
      clientId: clientId,
    );
    if (!mounted) return;
    if (client == null) {
      setState(() => _error = 'No se encontró la ficha del cliente.');
      return;
    }

    final updated = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => ClientDetailScreen(
          client: client,
          campaignId: campaignId,
          section: section,
        ),
      ),
    );

    if (updated == true && mounted) {
      await _loadRoutes();
    }
  }



  Future<void> _openNextClient(Map<String, dynamic> route) async {

    final rawClientes = (route['clientes'] as List?) ?? const [];

    if (rawClientes.isEmpty) {

      setState(() => _error = 'Esta ruta no tiene clientes.');

      return;

    }



    await _locationService.getCurrentPosition();

    final myLat = _locationService.latitude;

    final myLng = _locationService.longitude;

    if (myLat == null || myLng == null) {

      setState(() => _error = _locationService.error ?? 'No se pudo obtener GPS actual.');

      return;

    }



    final withCoords = rawClientes

        .map((raw) => raw is Map ? raw.map((k, v) => MapEntry(k.toString(), v)) : <String, dynamic>{})

        .where((c) => (c['lat'] as num?) != null && (c['lng'] as num?) != null)

        .toList();



    if (withCoords.isEmpty) {

      setState(() => _error = 'No hay clientes con coordenadas en esta ruta.');

      return;

    }



    Map<String, dynamic>? nearest;

    double best = double.infinity;

    for (final c in withCoords) {

      final lat = (c['lat'] as num).toDouble();

      final lng = (c['lng'] as num).toDouble();

      final d = Geolocator.distanceBetween(myLat, myLng, lat, lng);

      if (d < best) {

        best = d;

        nearest = c;

      }

    }



    if (nearest == null) {

      setState(() => _error = 'No se pudo calcular el siguiente cliente.');

      return;

    }



    final lat = (nearest['lat'] as num).toDouble();

    final lng = (nearest['lng'] as num).toDouble();

    final name = nearest['nombre']?.toString() ?? 'Cliente';



    final uri = Uri.parse('https://www.google.com/maps/dir/?api=1&destination=$lat,$lng&travelmode=driving');

    await launchUrl(uri, mode: LaunchMode.externalApplication);

    if (!mounted) return;

    setState(() {

      _error = 'Navegando a $name (${(best / 1000).toStringAsFixed(2)} km).';

    });

  }



  Future<void> _openRouteInGoogleMaps(Map<String, dynamic> route) async {

    final clients = parseRouteClients(route['clientes'] as List?);

    if (clients.isEmpty) {

      setState(() => _error = 'No hay clientes con coordenadas en esta ruta.');

      return;

    }



    await _locationService.getCurrentPosition();

    final myLat = _locationService.latitude;

    final myLng = _locationService.longitude;

    LatLng? origin;

    if (myLat != null && myLng != null) {

      origin = LatLng(myLat, myLng);

    }



    final ordered = orderClientsByNearest(clients, origin);

    final clientStops = clientMapsToLatLng(ordered);



    try {

      final built = buildGoogleMapsDrivingUrl(

        clientStops: clientStops,

        origin: origin,

      );

      final launched = await launchUrl(

        built.uri,

        mode: LaunchMode.externalApplication,

      );

      if (!mounted) return;

      if (!launched) {

        setState(() => _error = 'No se pudo abrir Google Maps.');

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

      setState(() => _error = 'Error al abrir Google Maps: $e');

    }

  }



  List<Map<String, dynamic>> _normalizeRouteClients(List clientes) {

    return clientes

        .map((raw) => raw is Map

            ? raw.map((k, v) => MapEntry(k.toString(), v))

            : <String, dynamic>{})

        .toList();

  }



  String _routeKey(Map<String, dynamic> route) {

    return route['id']?.toString() ?? route['fecha']?.toString() ?? '';

  }



  List<Map<String, dynamic>> _flatSearchMatches() {

    if (_searchQuery.trim().isEmpty) return [];

    final seen = <String>{};

    final out = <Map<String, dynamic>>[];

    for (final route in _routes) {

      for (final c in _normalizeRouteClients(

          (route['clientes'] as List?) ?? const [])) {

        if (!matchesRouteClientMap(c, _searchQuery)) continue;

        final key = c['codigo_cliente']?.toString() ?? '';

        if (key.isEmpty || seen.contains(key)) continue;

        seen.add(key);

        out.add(c);

      }

    }

    out.sort((a, b) => (a['nombre']?.toString() ?? '')

        .compareTo(b['nombre']?.toString() ?? ''));

    return out;

  }



  Widget _buildClientRouteTile(Map<String, dynamic> c) {

    final nombre = c['nombre']?.toString() ?? 'Sin nombre';

    final codigo = c['codigo_cliente']?.toString() ?? '—';

    final estado = c['estado']?.toString() ?? 'pendiente';

    return ListTile(

      dense: true,

      leading: const Icon(Icons.person_pin_circle_outlined),

      title: Text(nombre),

      subtitle: Text('Cod: $codigo'),

      trailing: Text(

        estado,

        style: TextStyle(

          color: estado == 'pendiente'

              ? Colors.orange.shade800

              : Colors.green.shade700,

          fontWeight: FontWeight.w700,

        ),

      ),

      onTap: () => _openClientFromRoute(c),

    );

  }



  Widget _buildSearchResultsList() {

    final matches = _flatSearchMatches();

    final pageItems = _searchPagination.slice(matches);

    return RefreshIndicator(

      color: AppTheme.primaryColor,

      onRefresh: _loadRoutes,

      child: ListView(

        physics: const AlwaysScrollableScrollPhysics(),

        padding: const EdgeInsets.all(12),

        children: [

          Padding(

            padding: const EdgeInsets.only(bottom: 8),

            child: Text(

              '${matches.length} coincidencia${matches.length == 1 ? '' : 's'}'

              '${_searchPagination.needsBar ? ' · pág. ${_searchPagination.page + 1}/${_searchPagination.totalPages}' : ''}',

              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),

            ),

          ),

          if (matches.isEmpty)

            Padding(

              padding: EdgeInsets.only(

                  top: MediaQuery.of(context).size.height * 0.2),

              child: Center(

                child: Text(

                  'Sin coincidencias',

                  style: TextStyle(color: Colors.grey.shade600),

                ),

              ),

            )

          else

            ...pageItems.map(_buildClientRouteTile),

          ClientListPaginationBar(

            pagination: _searchPagination,

            onPageChanged: (page) =>

                setState(() => _searchPagination.goTo(page)),

          ),

        ],

      ),

    );

  }



  Widget _buildBanner(String text, Color bg, Color fg) {

    return Container(

      width: double.infinity,

      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),

      color: bg,

      child: Text(

        text,

        style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600),

      ),

    );

  }



  Widget _buildEmptyState() {

    return Center(

      child: Padding(

        padding: const EdgeInsets.all(24),

        child: Column(

          mainAxisSize: MainAxisSize.min,

          children: [

            Icon(Icons.route_outlined, size: 48, color: Colors.grey.shade400),

            const SizedBox(height: 12),

            Text(

              _error != null ? _error! : 'Aún no tienes rutas guardadas.',

              textAlign: TextAlign.center,

              style: TextStyle(

                fontSize: 15,

                fontWeight: FontWeight.w500,

                color: _error != null ? Colors.red.shade800 : Colors.grey.shade700,

              ),

            ),

            if (_error == null) ...[

              const SizedBox(height: 8),

              Text(

                'Selecciona clientes en el tab Mapa y pulsa Guardar.',

                textAlign: TextAlign.center,

                style: TextStyle(fontSize: 13, color: Colors.grey.shade600),

              ),

            ],

          ],

        ),

      ),

    );

  }



  Widget _buildRoutesList() {

    return RefreshIndicator(

      color: AppTheme.primaryColor,

      onRefresh: _loadRoutes,

      child: ListView.separated(

        physics: const AlwaysScrollableScrollPhysics(),

        padding: const EdgeInsets.all(12),

        itemCount: _routes.length,

        separatorBuilder: (_, __) => const SizedBox(height: 8),

        itemBuilder: (context, i) {

          final route = _routes[i];

          final clientes = (route['clientes'] as List?) ?? const [];

          return Card(

            child: ExpansionTile(

              leading: const Icon(Icons.route, color: AppTheme.primaryColor),

              title: Text(

                _routeDisplayTitle(route),

                style: const TextStyle(fontWeight: FontWeight.w700),

              ),

              subtitle: Text(_routeDisplaySubtitle(route)),

              trailing: _buildRouteMenu(route),

              children: [

                Padding(

                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),

                  child: Column(

                    children: [

                      Row(

                        children: [

                          Expanded(

                            child: ElevatedButton.icon(

                              onPressed: () => _openNextClient(route),

                              icon: const Icon(Icons.navigation_outlined, size: 18),

                              label: const Text('Siguiente cliente'),

                            ),

                          ),

                          const SizedBox(width: 8),

                          Expanded(

                            child: OutlinedButton.icon(

                              onPressed: () {

                                Navigator.push(

                                  context,

                                  MaterialPageRoute(

                                    builder: (_) => MyRouteMapScreen(route: route),

                                  ),

                                );

                              },

                              icon: const Icon(Icons.map_outlined, size: 18),

                              label: const Text('Ver mapa'),

                            ),

                          ),

                        ],

                      ),

                      const SizedBox(height: 8),

                      SizedBox(

                        width: double.infinity,

                        child: OutlinedButton.icon(

                          onPressed: () => _openRouteInGoogleMaps(route),

                          icon: const Icon(Icons.open_in_new, size: 18),

                          label: const Text('Abrir ruta en Google Maps'),

                        ),

                      ),

                    ],

                  ),

                ),

                if (clientes.isEmpty)

                  const ListTile(

                    dense: true,

                    title: Text('Ruta sin clientes registrados.'),

                  )

                else

                  Builder(

                    builder: (_) {

                      final routeKey = _routeKey(route);

                      final normalized = _normalizeRouteClients(clientes);

                      final pagination = ClientListPagination()

                        ..goTo(_routeClientPages[routeKey] ?? 0);

                      final visible = pagination.slice(normalized);

                      return Column(

                        children: [

                          ...visible.map(_buildClientRouteTile),

                          ClientListPaginationBar(

                            pagination: pagination,

                            compact: true,

                            onPageChanged: (page) => setState(

                                () => _routeClientPages[routeKey] = page),

                          ),

                        ],

                      );

                    },

                  ),

              ],

            ),

          );

        },

      ),

    );

  }



  @override

  Widget build(BuildContext context) {

    return Scaffold(

      appBar: AppBar(

        title: const Text('Mis rutas'),

        actions: [

          IconButton(

            tooltip: 'Buscar por fecha',

            onPressed: _loadingDate ? null : _pickDateAndLoad,

            icon: _loadingDate

                ? const SizedBox(

                    width: 18,

                    height: 18,

                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),

                  )

                : const Icon(Icons.calendar_month, color: Colors.white),

          ),

          IconButton(

            tooltip: 'Recargar',

            onPressed: _loading ? null : _loadRoutes,

            icon: const Icon(Icons.refresh, color: Colors.white),

          ),

        ],

      ),

      body: _loading

          ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryColor))

          : Column(

              children: [

                if (_warning != null)

                  _buildBanner(_warning!, Colors.blue.shade50, Colors.blue.shade900),

                if (_error != null && _routes.isNotEmpty)

                  _buildBanner(_error!, Colors.amber.shade50, Colors.amber.shade900),

                Padding(

                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),

                  child: TextField(

                    controller: _searchController,

                    decoration: InputDecoration(

                      hintText: 'Buscar cliente por nombre, código o DNI…',

                      prefixIcon: const Icon(Icons.search, size: 20),

                      suffixIcon: _searchQuery.isNotEmpty

                          ? IconButton(

                              icon: const Icon(Icons.clear, size: 18),

                              onPressed: () {

                                _searchController.clear();

                                setState(() {

                                  _searchQuery = '';

                                  _searchPagination.reset();

                                });

                              },

                            )

                          : null,

                      isDense: true,

                      border: const OutlineInputBorder(),

                    ),

                    onChanged: (v) => setState(() {

                      _searchQuery = v;

                      _searchPagination.reset();

                    }),

                  ),

                ),

                Expanded(

                  child: _routes.isEmpty

                      ? RefreshIndicator(

                          color: AppTheme.primaryColor,

                          onRefresh: _loadRoutes,

                          child: SingleChildScrollView(

                            physics: const AlwaysScrollableScrollPhysics(),

                            child: SizedBox(

                              height: MediaQuery.of(context).size.height * 0.6,

                              child: _buildEmptyState(),

                            ),

                          ),

                        )

                      : _searchQuery.trim().isNotEmpty

                          ? _buildSearchResultsList()

                          : _buildRoutesList(),

                ),

              ],

            ),

    );

  }

}

