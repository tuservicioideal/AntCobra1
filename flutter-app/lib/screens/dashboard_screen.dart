import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/client_model.dart';
import '../models/notification_model.dart';
import '../services/auth_service.dart';
import '../services/campana_banco_filter_notifier.dart';
import '../services/campaign_service.dart';
import '../services/firestore_service.dart';
import '../services/notification_service.dart';
import '../services/document_download_service.dart';
import '../services/letter_jpg_publish_service.dart';
import '../services/letter_template_cache_service.dart';
import '../services/letter_word_service.dart';
import '../services/share_print_service.dart';
import '../services/location_service.dart';
import '../services/tracking_service.dart';
import '../services/etiqueta_catalog_service.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/client_list_pagination.dart';
import '../utils/client_proximity_sort.dart';
import '../utils/local_file_payload.dart';
import '../widgets/campana_banco_filter_bar.dart';
import '../widgets/stat_card.dart';
import '../widgets/client_list_tile.dart';
import '../widgets/client_list_pagination_bar.dart';
import '../widgets/paginated_client_checkbox_list.dart';
import '../utils/responsive.dart';
import '../widgets/master_detail_scaffold.dart';
import '../widgets/stats/stats_shared_sections.dart';
import 'client_detail_screen.dart';
import 'notifications_screen.dart';

/// Extract a human-friendly geo label from a composite key like '01_1211_H'.
String _geoLabel(String key) {
  final parts = key.split('_');
  if (parts.length == 3) {
    return 'R${parts[0]} · Z${parts[1]} · Sección ${parts[2]}';
  }
  return 'Sección $key';
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _campaignService = CampaignService();
  final _firestoreService = FirestoreService();
  final _notificationService = NotificationService();
  final _downloadService = DocumentDownloadService();
  final _sharePrintService = SharePrintService();
  final _letterJpgPublishService = LetterJpgPublishService();
  final _letterWordService = LetterWordService();
  final _letterTemplateCache = LetterTemplateCacheService();
  final _etiquetaCatalog = EtiquetaCatalogService();
  final _searchController = TextEditingController();

  String? _campaignId;
  Map<String, dynamic>? _campaignData;
  String? _section;
  String? _sectionFilter; // null = all assigned sections
  List<String> _availableSections = [];
  List<String> _gestorSecciones = []; // user's assigned composite keys
  List<ClientModel> _clients = [];
  Map<String, dynamic> _catalog = {}; // territorial catalog
  bool _loading = true;
  String _filter = 'all'; // all, pendiente, visitado
  final Set<String> _etiquetaFilter = {};
  String _searchQuery = '';
  bool _isGestorRole = true;
  double? _sortOriginLat;
  double? _sortOriginLng;
  final _pagination = ClientListPagination();
  String? _selectedClientId;
  bool _tableView = false;

  CampanaBancoFilterNotifier? _campanaFilterNotifier;
  StreamSubscription<List<ClientModel>>? _clientsSub;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _loadData();
    });
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
    if (mounted) {
      _pagination.reset();
      setState(() {});
    }
  }

  void _resetPagination() {
    _pagination.reset();
  }

  @override
  void dispose() {
    _clientsSub?.cancel();
    _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() => _loading = true);

    final auth = context.read<AuthService>();
    final profile = auth.profile;

    // 1. Get campaign
    final campaignId = await _campaignService.getActiveCampaignId();
    if (campaignId == null) {
      setState(() => _loading = false);
      return;
    }

    _campaignId = campaignId;
    _campaignData = await _campaignService.getCampaignData(campaignId);
    unawaited(_letterTemplateCache.prefetchTemplates());

    // Load territorial catalog for hierarchical section display
    _catalog = await _firestoreService.getEstructuraTerritorial();

    // 2. Discover section(s) — prefer secciones array (composite keys)
    final List<String> profileSecciones = profile?.secciones ?? [];
    String? section = profile?.seccion;
    _gestorSecciones = profileSecciones;
    _sectionFilter = null; // reset filter on reload

    // For gestor role: only show their assigned sections
    // For admin/supervisor: show all campaign sections
    final isGestor = profile?.isGestor ?? true;
    if (isGestor && profileSecciones.isNotEmpty) {
      _availableSections = profileSecciones.toList()..sort();
    } else {
      final allSections =
          await _campaignService.getAvailableSections(campaignId);
      _availableSections = allSections;
    }

    if (isGestor && profileSecciones.isNotEmpty) {
      _section = profileSecciones.first;
    } else if (!isGestor && _availableSections.isNotEmpty) {
      _section = _availableSections.first;
    } else {
      if (section == null || section.isEmpty) {
        if (_availableSections.isNotEmpty) section = _availableSections.first;
      }
      _section = section;
    }

    _startClientsStream();

    await _etiquetaCatalog.loadCatalogo();
    await _refreshSortOrigin();
    if (mounted) {
      context.read<CampanaBancoFilterNotifier>().updateAvailable(_clients);
      setState(() => _loading = false);
    }
  }

  void _startClientsStream() {
    _clientsSub?.cancel();
    if (_campaignId == null) return;

    final auth = context.read<AuthService>();
    final profile = auth.profile;
    final isGestor = profile?.isGestor ?? true;
    final profileSecciones = profile?.secciones ?? [];

    final List<String> sections;
    if (isGestor && profileSecciones.isNotEmpty) {
      sections = profileSecciones;
    } else if (!isGestor && _availableSections.isNotEmpty) {
      sections = _availableSections;
    } else if (_section != null && _section!.isNotEmpty) {
      sections = [_section!];
    } else {
      return;
    }

    _clientsSub = _firestoreService
        .streamClientsMultiSection(_campaignId!, sections)
        .listen((clients) {
      if (!mounted) return;
      _clients = clients;
      context.read<CampanaBancoFilterNotifier>().updateAvailable(_clients);
      setState(() => _loading = false);
    }, onError: (e) {
      debugPrint('Client stream error: $e');
      if (mounted) setState(() => _loading = false);
    });
  }

  Future<void> _refreshSortOrigin() async {
    if (!mounted) return;
    final profile = context.read<AuthService>().profile;
    _isGestorRole = profile?.isGestor ?? true;
    if (!_isGestorRole) {
      _sortOriginLat = null;
      _sortOriginLng = null;
      return;
    }

    final location = context.read<LocationService>();
    var pos = location.lastPosition;
    pos ??= context.read<TrackingService>().currentPosition;
    pos ??= await location.getCurrentPosition();
    if (!mounted) return;

    if (pos != null) {
      _sortOriginLat = pos.latitude;
      _sortOriginLng = pos.longitude;
    } else {
      _sortOriginLat = null;
      _sortOriginLng = null;
    }
  }

  bool get _isCallGestor =>
      context.read<AuthService>().profile?.isCallGestor ?? false;

  List<ClientModel> _filteredClients(String? campanaFilter) {
    var list = _clients.where((c) => c.isActiveForGestor).toList();
    list = applyCampanaBancoFilter(list, campanaFilter);

    // Apply section filter (client-side)
    if (_sectionFilter != null) {
      list = list.where((c) => c.seccionKey == _sectionFilter).toList();
    }

    // Apply status filter
    if (_filter == 'pendiente') {
      list = list.where((c) => c.isPendiente).toList();
    } else if (_filter == 'visitado') {
      list = list.where((c) => c.isVisitado).toList();
    } else if (_filter == 'promesa') {
      list = list.where((c) => c.hasPromesa).toList();
    }

    if (_etiquetaFilter.isNotEmpty) {
      list = list.where((c) {
        return c.etiquetas.any((id) => _etiquetaFilter.contains(id));
      }).toList();
    }

    // Apply search
    if (_searchQuery.isNotEmpty) {
      list = list
          .where((c) => matchesClientSearch(c, _searchQuery))
          .toList();
    }

    if (_isCallGestor) {
      list.sort((a, b) {
        if (a.isPendiente != b.isPendiente) {
          return a.isPendiente ? -1 : 1;
        }
        return b.importeDeudaPendiente.compareTo(a.importeDeudaPendiente);
      });
    } else if (_isGestorRole &&
        _sortOriginLat != null &&
        _sortOriginLng != null) {
      list = sortClientsByProximity(
        list,
        originLat: _sortOriginLat!,
        originLng: _sortOriginLng!,
        pendingFirst: true,
      );
    }

    return list;
  }

  // Stats — reflect campaña + section filters
  List<ClientModel> _sectionClients(String? campanaFilter) {
    var base = _clients.where((c) => c.isActiveForGestor).toList();
    base = applyCampanaBancoFilter(base, campanaFilter);
    if (_sectionFilter == null) return base;
    return base.where((c) => c.seccionKey == _sectionFilter).toList();
  }

  int _totalClients(List<ClientModel> sectionClients) => sectionClients.length;
  int _pendientes(List<ClientModel> sectionClients) =>
      sectionClients.where((c) => c.isPendiente).length;
  int _visitados(List<ClientModel> sectionClients) =>
      sectionClients.where((c) => c.isVisitado).length;
  int _promesas(List<ClientModel> sectionClients) =>
      sectionClients.where((c) => c.hasPromesa).length;
  double _montoCartera(List<ClientModel> sectionClients) => sectionClients.fold(
        0.0,
        (sum, c) => sum + c.importeDeudaPendiente,
      );
  double _avance(List<ClientModel> sectionClients) {
    final total = sectionClients.length;
    final visitados = sectionClients.where((c) => c.isVisitado).length;
    return total > 0 ? (visitados / total * 100) : 0;
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    final profile = auth.profile;
    final isGestor = profile?.isGestor ?? true;
    final isCallGestor = profile?.isCallGestor ?? false;
    final campanaFilterNotifier = context.watch<CampanaBancoFilterNotifier>();
    final campanaFilter = campanaFilterNotifier.selected;
    final sectionClients = _sectionClients(campanaFilter);
    final filteredClients = _filteredClients(campanaFilter);
    final pageClients = _pagination.slice(filteredClients);
    final campanaSubtitle = campanaFilter != null
        ? '${campanaBancoFilterLabel(campanaFilter)} · ${_totalClients(sectionClients)} cuentas'
        : null;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              isCallGestor
                  ? 'Call Center'
                  : 'Gestión de Cobranza',
            ),
            if (_section != null)
              Text(
                campanaSubtitle ??
                    (isCallGestor
                        ? 'Mi cartera · ${_totalClients(sectionClients)} cuentas'
                        : _sectionFilter != null
                            ? _geoLabel(_sectionFilter!)
                            : _gestorSecciones.length > 1
                                ? '${_gestorSecciones.length} secciones asignadas'
                                : _geoLabel(_section!)),
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w400,
                  color: Colors.white.withValues(alpha: 0.8),
                ),
              ),
          ],
        ),
        actions: [
          if (context.isExpanded)
            IconButton(
              icon: Icon(
                _tableView ? Icons.view_list : Icons.table_rows_outlined,
                color: Colors.white,
              ),
              tooltip: _tableView ? 'Vista lista' : 'Vista tabla',
              onPressed: () => setState(() => _tableView = !_tableView),
            ),
          if (isGestor && !isCallGestor)
            IconButton(
              icon: const Icon(Icons.description_outlined, color: Colors.white),
              tooltip: 'Cartas Word (masivo)',
              onPressed: filteredClients.isEmpty ? null : _openBulkWordDialog,
            ),
          // JPG masivo oculto — fase actual: solo Word (.docx)
          // Notification bell with unread badge
          StreamBuilder<List<NotificationModel>>(
            stream: _notificationService.streamNotifications(
              auth.firebaseUser?.uid ?? '',
            ),
            builder: (context, snapshot) {
              final unread = (snapshot.data ?? [])
                  .where((n) => !n.leida)
                  .length;
              return IconButton(
                icon: Badge(
                  isLabelVisible: unread > 0,
                  label: Text(
                    unread > 9 ? '9+' : '$unread',
                    style: const TextStyle(fontSize: 10),
                  ),
                  child: const Icon(
                    Icons.notifications_outlined,
                    color: Colors.white,
                  ),
                ),
                tooltip: 'Notificaciones',
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => NotificationsScreen(
                        uid: auth.firebaseUser?.uid ?? '',
                      ),
                    ),
                  );
                },
              );
            },
          ),
          if (campanaFilterNotifier.hasActiveFilter)
            IconButton(
              icon: const Icon(Icons.layers_clear, color: Colors.white),
              tooltip: 'Quitar filtro de campaña',
              onPressed: campanaFilterNotifier.reset,
            ),
          // Section filter (if multiple sections)
          if (_availableSections.length > 1)
            PopupMenuButton<String>(
              icon: Icon(
                _sectionFilter != null
                    ? Icons.filter_alt
                    : Icons.filter_alt_outlined,
                color: Colors.white,
              ),
              tooltip: 'Filtrar por sección',
              onSelected: (section) {
                setState(() {
                  _resetPagination();
                  if (section == '_all_') {
                    _sectionFilter = null;
                    _section = _gestorSecciones.isNotEmpty
                        ? _gestorSecciones.first
                        : _availableSections.first;
                  } else {
                    _sectionFilter = section;
                    _section = section;
                  }
                });
              },
              itemBuilder: (_) => _buildSectionMenuItems(),
            ),
          // Refresh
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            tooltip: 'Actualizar',
            onPressed: _loadData,
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppTheme.primaryColor))
          : context.isExpanded
              ? _buildExpandedBody(
                  isCallGestor: isCallGestor,
                  sectionClients: sectionClients,
                  filteredClients: filteredClients,
                  pageClients: pageClients,
                  campanaFilterNotifier: campanaFilterNotifier,
                  campanaFilter: campanaFilter,
                )
              : RefreshIndicator(
              color: AppTheme.primaryColor,
              onRefresh: _loadData,
              child: CustomScrollView(
                slivers: _buildDashboardSlivers(
                  isCallGestor: isCallGestor,
                  sectionClients: sectionClients,
                  filteredClients: filteredClients,
                  pageClients: pageClients,
                  campanaFilterNotifier: campanaFilterNotifier,
                  campanaFilter: campanaFilter,
                ),
              ),
            ),
    );
  }

  List<Widget> _buildDashboardSlivers({
    required bool isCallGestor,
    required List<ClientModel> sectionClients,
    required List<ClientModel> filteredClients,
    required List<ClientModel> pageClients,
    required CampanaBancoFilterNotifier campanaFilterNotifier,
    required String? campanaFilter,
  }) {
    return [
      if (isCallGestor)
        SliverToBoxAdapter(
          child: _buildCallCenterBanner(sectionClients),
        ),
      if (_campaignData != null && !isCallGestor)
        SliverToBoxAdapter(
          child: TramoProgressBar(clients: sectionClients),
        ),
      SliverToBoxAdapter(
        child: isCallGestor
            ? _buildCallStatsRow(sectionClients, compact: false)
            : _buildStatsRow(sectionClients, compact: false),
      ),
      SliverToBoxAdapter(
        child: CampanaBancoFilterBar(
          available: campanaFilterNotifier.available,
          selected: campanaFilter,
          onSelected: (value) {
            campanaFilterNotifier.select(value);
          },
        ),
      ),
      SliverToBoxAdapter(
        child: _buildSearchAndFilter(filteredClients),
      ),
      if (filteredClients.isEmpty)
        SliverFillRemaining(child: _buildEmptyState())
      else
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (context, index) => _buildClientListItem(
              pageClients[index],
              isCallGestor: isCallGestor,
              campanaFilterNotifier: campanaFilterNotifier,
              campanaFilter: campanaFilter,
              index: index,
            ),
            childCount: pageClients.length,
          ),
        ),
      if (filteredClients.isNotEmpty)
        SliverToBoxAdapter(
          child: ClientListPaginationBar(
            pagination: _pagination,
            onPageChanged: (page) => setState(() => _pagination.goTo(page)),
          ),
        ),
      const SliverToBoxAdapter(child: SizedBox(height: 20)),
    ];
  }

  Widget _buildExpandedBody({
    required bool isCallGestor,
    required List<ClientModel> sectionClients,
    required List<ClientModel> filteredClients,
    required List<ClientModel> pageClients,
    required CampanaBancoFilterNotifier campanaFilterNotifier,
    required String? campanaFilter,
  }) {
    ClientModel? selectedClient;
    if (_selectedClientId != null) {
      final matches =
          filteredClients.where((c) => c.id == _selectedClientId);
      if (matches.isNotEmpty) selectedClient = matches.first;
    }

    return MasterDetailScaffold(
      header: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (isCallGestor) _buildCallCenterBanner(sectionClients),
            if (_campaignData != null && !isCallGestor)
              TramoProgressBar(clients: sectionClients),
            isCallGestor
                ? _buildCallStatsRow(sectionClients, compact: true)
                : _buildStatsRow(sectionClients, compact: true),
            CampanaBancoFilterBar(
              available: campanaFilterNotifier.available,
              selected: campanaFilter,
              onSelected: campanaFilterNotifier.select,
            ),
            _buildSearchAndFilter(filteredClients),
          ],
        ),
      ),
      master: RefreshIndicator(
        color: AppTheme.primaryColor,
        onRefresh: _loadData,
        child: filteredClients.isEmpty
            ? ListView(children: [_buildEmptyState()])
            : Column(
                children: [
                  if (_tableView) _buildTableHeader(isCallGestor),
                  Expanded(
                    child: ListView.builder(
                      itemCount: pageClients.length,
                      itemBuilder: (context, index) => _buildClientListItem(
                        pageClients[index],
                        isCallGestor: isCallGestor,
                        campanaFilterNotifier: campanaFilterNotifier,
                        campanaFilter: campanaFilter,
                        index: index,
                        tableView: _tableView,
                      ),
                    ),
                  ),
                  ClientListPaginationBar(
                    pagination: _pagination,
                    onPageChanged: (page) =>
                        setState(() => _pagination.goTo(page)),
                  ),
                ],
              ),
      ),
      detail: selectedClient == null
          ? null
          : ClientDetailScreen(
              key: ValueKey(selectedClient.id),
              client: selectedClient,
              campaignId: _campaignId!,
              section: selectedClient.seccionKey.isNotEmpty
                  ? selectedClient.seccionKey
                  : _section!,
              embedded: true,
              onUpdated: _reloadClients,
            ),
      emptyDetail: const MasterDetailEmptyPlaceholder(
        subtitle: 'Elige una cuenta de la lista para gestionarla sin salir del panel.',
      ),
    );
  }

  Widget _buildTableHeader(bool isCallGestor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: Colors.grey.shade100,
      child: Row(
        children: [
          const Expanded(
            flex: 3,
            child: Text('Cliente', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 11)),
          ),
          Expanded(
            flex: 2,
            child: Text(
              isCallGestor ? 'Teléfono' : 'DNI',
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 11),
            ),
          ),
          const Expanded(
            child: Text('Deuda', textAlign: TextAlign.end, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 11)),
          ),
          const SizedBox(width: 8),
          const SizedBox(
            width: 88,
            child: Text('Estado', textAlign: TextAlign.end, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 11)),
          ),
        ],
      ),
    );
  }

  Widget _buildClientListItem(
    ClientModel client, {
    required bool isCallGestor,
    required CampanaBancoFilterNotifier campanaFilterNotifier,
    required String? campanaFilter,
    required int index,
    bool tableView = false,
  }) {
    final isSelected = _selectedClientId == client.id;
    final onTap = () => _openClientDetail(client);

    if (tableView) {
      return ClientDataRow(
        client: client,
        isCallMode: isCallGestor,
        isSelected: isSelected,
        distanceLabel: isCallGestor
            ? null
            : distanceLabelForClient(client, _sortOriginLat, _sortOriginLng),
        onTap: onTap,
      );
    }

    return ClientListTile(
      client: client,
      isCallMode: isCallGestor,
      isSelected: isSelected,
      showChevron: !context.isExpanded,
      etiquetaCatalog: _etiquetaCatalog,
      showCampanaBadge:
          campanaFilterNotifier.showFilterBar && campanaFilter == null,
      distanceLabel: isCallGestor
          ? null
          : distanceLabelForClient(client, _sortOriginLat, _sortOriginLng),
      onTap: onTap,
    )
        .animate()
        .fadeIn(
          delay: Duration(milliseconds: (index * 30).clamp(0, 300)),
          duration: 300.ms,
        )
        .slideX(begin: 0.05, end: 0, duration: 300.ms);
  }

  Widget _buildCallCenterBanner(List<ClientModel> sectionClients) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryColor.withValues(alpha: 0.12),
            Colors.teal.withValues(alpha: 0.08),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Icon(Icons.headset_mic, color: AppTheme.primaryColor, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Gestión telefónica · Tramo 1',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Cartera S/ ${_montoCartera(sectionClients).toStringAsFixed(0)} · '
                  'priorice pendientes con mayor deuda',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCallStatsRow(List<ClientModel> sectionClients, {bool compact = false}) {
    final cards = [
      StatCard(
        label: 'Cartera',
        value: '${_totalClients(sectionClients)}',
        icon: Icons.people_outline,
        color: AppTheme.primaryColor,
        small: compact,
      ),
      StatCard(
        label: 'Pendientes',
        value: '${_pendientes(sectionClients)}',
        icon: Icons.phone_in_talk_outlined,
        color: Colors.amber.shade700,
        small: compact,
      ),
      StatCard(
        label: 'Contactados',
        value: '${_visitados(sectionClients)}',
        icon: Icons.check_circle_outline,
        color: Colors.green.shade600,
        small: compact,
      ),
      StatCard(
        label: 'Promesas',
        value: '${_promesas(sectionClients)}',
        icon: Icons.event_available_outlined,
        color: AppTheme.accentColor,
        small: compact,
      ),
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: compact
          ? Wrap(
              spacing: 8,
              runSpacing: 8,
              children: cards
                  .map((c) => SizedBox(width: 160, child: c))
                  .toList(),
            )
          : Row(
              children: cards.map((c) => Expanded(child: c)).toList(),
            ),
    );
  }

  Widget _buildStatsRow(List<ClientModel> sectionClients, {bool compact = false}) {
    final cards = [
      StatCard(
        label: 'Total',
        value: '${_totalClients(sectionClients)}',
        icon: Icons.people_outline,
        color: AppTheme.primaryColor,
        small: compact,
      ),
      StatCard(
        label: 'Pendientes',
        value: '${_pendientes(sectionClients)}',
        icon: Icons.pending_outlined,
        color: Colors.amber.shade700,
        small: compact,
      ),
      StatCard(
        label: 'Visitados',
        value: '${_visitados(sectionClients)}',
        icon: Icons.check_circle_outline,
        color: Colors.green.shade600,
        small: compact,
      ),
      StatCard(
        label: 'Avance',
        value: '${_avance(sectionClients).toStringAsFixed(0)}%',
        icon: Icons.trending_up,
        color: AppTheme.accentColor,
        small: compact,
      ),
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: compact
          ? Wrap(
              spacing: 8,
              runSpacing: 8,
              children: cards
                  .map((c) => SizedBox(width: 160, child: c))
                  .toList(),
            )
          : Row(
              children: cards.map((c) => Expanded(child: c)).toList(),
            ),
    );
  }

  Widget _buildSearchAndFilter(List<ClientModel> filteredClients) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: Column(
        children: [
          // Search bar
          TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: _isCallGestor
                  ? 'Buscar por nombre, DNI, teléfono...'
                  : 'Buscar por nombre, DNI, código...',
              prefixIcon: const Icon(Icons.search, size: 20),
              suffixIcon: _searchQuery.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, size: 18),
                      onPressed: () {
                        _searchController.clear();
                        setState(() {
                          _searchQuery = '';
                          _resetPagination();
                        });
                      },
                    )
                  : null,
              contentPadding:
                  const EdgeInsets.symmetric(vertical: 0, horizontal: 16),
              filled: true,
              fillColor: Colors.grey.shade50,
            ),
            onChanged: (v) => setState(() {
              _searchQuery = v;
              _resetPagination();
            }),
          ),

          const SizedBox(height: 10),

          // Filter tabs
          Row(
            children: [
              _buildFilterChip('all', 'Todos', Icons.list),
              const SizedBox(width: 8),
              _buildFilterChip(
                  'pendiente', 'Pendientes', Icons.pending_outlined),
              const SizedBox(width: 8),
              _buildFilterChip(
                  'visitado',
                  _isCallGestor ? 'Contactados' : 'Visitados',
                  Icons.check_circle_outline),
              if (_isCallGestor) ...[
                const SizedBox(width: 8),
                _buildFilterChip(
                    'promesa', 'Promesas', Icons.event_available_outlined),
              ],
              const Spacer(),
              Text(
                _pagination.needsBar
                    ? '${filteredClients.length} clientes · pág. ${_pagination.page + 1}/${_pagination.totalPages}'
                    : '${filteredClients.length} clientes',
                style: TextStyle(
                  color: Colors.grey.shade500,
                  fontSize: 12,
                ),
              ),
            ],
          ),

          if (_etiquetaCatalog.etiquetas.isNotEmpty) ...[
            const SizedBox(height: 8),
            SizedBox(
              height: 34,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: _etiquetaCatalog.etiquetas.map((tag) {
                  final active = _etiquetaFilter.contains(tag.id);
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(tag.nombre, style: const TextStyle(fontSize: 11)),
                      selected: active,
                      selectedColor: tag.color.withValues(alpha: 0.25),
                      checkmarkColor: tag.color,
                      visualDensity: VisualDensity.compact,
                      onSelected: (v) => setState(() {
                        if (v) {
                          _etiquetaFilter.add(tag.id);
                        } else {
                          _etiquetaFilter.remove(tag.id);
                        }
                        _resetPagination();
                      }),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFilterChip(String value, String label, IconData icon) {
    final isActive = _filter == value;
    return GestureDetector(
      onTap: () => setState(() {
        _filter = value;
        _resetPagination();
      }),
      child: AnimatedContainer(
        duration: 200.ms,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isActive
              ? AppTheme.primaryColor
              : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isActive
                ? AppTheme.primaryColor
                : Colors.grey.shade300,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 14,
              color: isActive ? Colors.white : Colors.grey.shade600,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: isActive ? Colors.white : Colors.grey.shade600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.inbox_outlined, size: 64, color: Colors.grey.shade300),
          const SizedBox(height: 16),
          Text(
            _searchQuery.isNotEmpty
                ? 'No se encontraron resultados'
                : 'No hay clientes para mostrar',
            style: TextStyle(
              color: Colors.grey.shade500,
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }

  /// Build hierarchical section menu items grouped by region/zona.
  List<PopupMenuEntry<String>> _buildSectionMenuItems() {
    final items = <PopupMenuEntry<String>>[];
    final isGestor = context.read<AuthService>().profile?.isGestor ?? true;
    final allSectionsLabel =
        isGestor ? 'Todas mis secciones' : 'Toda la campaña';

    // "All sections" option at top
    final allSelected = _sectionFilter == null;
    items.add(PopupMenuItem<String>(
      value: '_all_',
      child: Row(
        children: [
          Icon(
            allSelected ? Icons.select_all : Icons.select_all,
            size: 18,
            color: allSelected ? AppTheme.primaryColor : Colors.grey,
          ),
          const SizedBox(width: 8),
          Text(
            allSectionsLabel,
            style: TextStyle(
              fontWeight: allSelected ? FontWeight.bold : FontWeight.normal,
              color: allSelected ? AppTheme.primaryColor : null,
            ),
          ),
        ],
      ),
    ));
    items.add(const PopupMenuDivider());

    // If catalog is available, group sections hierarchically
    if (_catalog.isNotEmpty) {
      final regions = _catalog.keys.toList()..sort();

      for (final region in regions) {
        final regionSections = _availableSections
            .where((s) => s.startsWith('${region}_'))
            .toList();
        if (regionSections.isEmpty) continue;

        // Region header
        items.add(PopupMenuItem<String>(
          enabled: false,
          height: 32,
          child: Text(
            'Región $region',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 13,
              color: AppTheme.primaryColor,
            ),
          ),
        ));

        final zonas = (_catalog[region] as Map<String, dynamic>?)?['zonas'];
        if (zonas is Map<String, dynamic>) {
          final zonaKeys = zonas.keys.toList()..sort();
          for (final zona in zonaKeys) {
            final zonaSections = regionSections
                .where((s) => s.startsWith('${region}_${zona}_'))
                .toList()
              ..sort();
            if (zonaSections.isEmpty) continue;

            for (final sec in zonaSections) {
              final isSelected = sec == _sectionFilter;
              items.add(PopupMenuItem<String>(
                value: sec,
                child: Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Row(
                    children: [
                      Icon(
                        isSelected
                            ? Icons.check_circle
                            : Icons.circle_outlined,
                        size: 16,
                        color: isSelected ? AppTheme.primaryColor : Colors.grey,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'Z$zona · Sección ${sec.split('_').last}',
                        style: TextStyle(
                          fontWeight:
                              isSelected ? FontWeight.bold : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              ));
            }
          }
        }
      }

      if (items.length > 2) return items; // has items beyond "all" + divider
    }

    // Fallback: flat list (remove catalog-based items, keep "all" + divider)
    for (final s in _availableSections) {
      final isSelected = s == _sectionFilter;
      items.add(PopupMenuItem<String>(
        value: s,
        child: Row(
          children: [
            Icon(
              isSelected ? Icons.check_circle : Icons.circle_outlined,
              size: 18,
              color: isSelected ? AppTheme.primaryColor : Colors.grey,
            ),
            const SizedBox(width: 8),
            Text(
              _geoLabel(s),
              style: TextStyle(
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ],
        ),
      ));
    }
    return items;
  }

  /// Tras editar un cliente el stream de Firestore actualiza la lista.
  Future<void> _reloadClients() async {
    await _refreshSortOrigin();
    if (mounted) setState(() {});
  }

  void _openClientDetail(ClientModel client) async {
    if (context.isExpanded) {
      setState(() => _selectedClientId = client.id);
      return;
    }

    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => ClientDetailScreen(
          client: client,
          campaignId: _campaignId!,
          section: client.seccionKey.isNotEmpty ? client.seccionKey : _section!,
        ),
      ),
    );

    // Refresh if client was updated
    if (result == true) {
      _reloadClients();
    }
  }

  Future<void> _openBulkWordDialog() async {
    final selected = <String>{};
    bool working = false;
    var progress = 0;
    var total = 0;

    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setLocalState) {
            final clients = _filteredClients(
              context.read<CampanaBancoFilterNotifier>().selected,
            );
            final auth = context.read<AuthService>();

            Future<void> runGenerate({required bool onlySelected}) async {
              final targets = onlySelected
                  ? clients.where((c) => selected.contains(c.id)).toList()
                  : clients;
              if (targets.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('No hay clientes seleccionados.')),
                );
                return;
              }
              setLocalState(() {
                working = true;
                progress = 0;
                total = targets.length;
              });
              final result = await _letterWordService.generateWordCombined(
                clients: targets,
                gestorName: auth.profile?.nombre ?? '',
                gestorPhone: auth.profile?.telefono ?? '',
                campaignName: _campaignData?['nombre']?.toString() ?? '',
                onProgress: (current, t) {
                  setLocalState(() {
                    progress = current;
                    total = t;
                  });
                },
              );
              if (!mounted) return;
              setLocalState(() => working = false);
              if (result.payload == null || result.letterCount == 0) {
                ScaffoldMessenger.of(this.context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'No se generaron cartas Word. Verifique plantillas en Firebase.',
                    ),
                  ),
                );
                return;
              }
              await _sharePrintService.sharePayload(result.payload!);
              if (mounted) {
                var message =
                    'Se generó 1 documento con ${result.letterCount} carta'
                    '${result.letterCount == 1 ? '' : 's'}.';
                if (result.failedCount > 0) {
                  message +=
                      ' ${result.failedCount} cliente(s) omitido(s) por error.';
                }
                if (result.mixedTemplates) {
                  message +=
                      ' Algunos clientes usaron plantillas distintas por tramo.';
                }
                ScaffoldMessenger.of(this.context).showSnackBar(
                  SnackBar(content: Text(message)),
                );
              }
            }

            return AlertDialog(
              title: const Text('Generar cartas Word'),
              content: ConstrainedBox(
                constraints: BoxConstraints(
                  maxWidth: context.dialogMaxWidth(520),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Genera un documento Word con todas las cartas seleccionadas, '
                      'listo para imprimir. No se sube a Firebase.',
                      style: TextStyle(fontSize: 12),
                    ),
                    if (working && total > 0) ...[
                      const SizedBox(height: 10),
                      LinearProgressIndicator(value: progress / total),
                      Text('$progress / $total', style: const TextStyle(fontSize: 12)),
                    ],
                    const SizedBox(height: 10),
                    PaginatedClientCheckboxList(
                      clients: clients,
                      selected: selected,
                      enabled: !working,
                      onSelectionChanged: (next) =>
                          setLocalState(() => selected
                            ..clear()
                            ..addAll(next)),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: working ? null : () => Navigator.pop(ctx),
                  child: const Text('Cerrar'),
                ),
                TextButton(
                  onPressed: working ? null : () => runGenerate(onlySelected: true),
                  child: const Text('Generar seleccionadas'),
                ),
                ElevatedButton(
                  onPressed: working ? null : () => runGenerate(onlySelected: false),
                  child: Text(working ? 'Procesando…' : 'Generar todas'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _openBulkLettersDialog() async {
    final selected = <String>{};
    bool working = false;
    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setLocalState) {
            final clients = _filteredClients(
              context.read<CampanaBancoFilterNotifier>().selected,
            );
            Future<void> runDownload({required bool onlySelected}) async {
              final targets = onlySelected
                  ? clients.where((c) => selected.contains(c.id)).toList()
                  : clients;
              if (targets.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('No hay clientes seleccionados.')),
                );
                return;
              }
              setLocalState(() => working = true);
              final count = await _downloadLettersForClients(targets);
              if (!mounted) return;
              setLocalState(() => working = false);
              ScaffoldMessenger.of(this.context).showSnackBar(
                SnackBar(content: Text('Se descargaron $count cartas JPG.')),
              );
            }

            return AlertDialog(
              title: const Text('Descarga masiva de cartas'),
              content: SizedBox(
                width: 520,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Puedes descargar todas las cartas visibles o seleccionar clientes específicos.',
                      style: TextStyle(fontSize: 12),
                    ),
                    const SizedBox(height: 10),
                    PaginatedClientCheckboxList(
                      clients: clients,
                      selected: selected,
                      enabled: !working,
                      onSelectionChanged: (next) =>
                          setLocalState(() => selected
                            ..clear()
                            ..addAll(next)),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: working ? null : () => Navigator.pop(ctx),
                  child: const Text('Cerrar'),
                ),
                TextButton(
                  onPressed: working ? null : () => runDownload(onlySelected: true),
                  child: const Text('Descargar seleccionadas'),
                ),
                ElevatedButton(
                  onPressed: working ? null : () => runDownload(onlySelected: false),
                  child: Text(working ? 'Procesando...' : 'Descargar todas'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<int> _downloadLettersForClients(List<ClientModel> clients) async {
    final auth = context.read<AuthService>();
    final payloads = <LocalFilePayload>[];
    for (final client in clients) {
      try {
        var letters = await _firestoreService.getClientLetters(
          campaignId: _campaignId!,
          clientId: client.codigoCliente.isNotEmpty ? client.codigoCliente : client.id,
          section: client.seccionKey.isNotEmpty ? client.seccionKey : (_section ?? ''),
        );
        if (letters.isEmpty) {
          letters = await _letterJpgPublishService.ensureLetterJpg(
            context: context,
            client: client,
            campaignId: _campaignId!,
            section: client.seccionKey.isNotEmpty ? client.seccionKey : (_section ?? ''),
            gestorName: auth.profile?.nombre ?? '',
            gestorPhone: auth.profile?.telefono ?? '',
            campaignName: _campaignData?['nombre']?.toString() ?? '',
          );
        }
        final files = await _downloadService.downloadLetters(letters);
        payloads.addAll(files);
      } catch (_) {
        // Continue with next client
      }
    }
    if (payloads.isNotEmpty) {
      await _sharePrintService.sharePayloads(payloads);
    }
    return payloads.length;
  }

}
