import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/campaign_stats.dart';
import '../services/auth_service.dart';
import '../services/campana_banco_filter_notifier.dart';
import '../services/campaign_service.dart';
import '../services/campaign_stats_service.dart';
import '../services/firestore_service.dart';
import '../services/notification_service.dart';
import '../models/notification_model.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/stats_format.dart';
import '../widgets/campana_banco_filter_bar.dart';
import '../widgets/stat_card.dart';
import '../widgets/stats/campana_banco_cards.dart';
import '../widgets/stats/contact_response_card.dart';
import '../widgets/stats/gestor_ranking_preview.dart';
import '../widgets/stats/stats_shared_sections.dart';
import '../widgets/stats/virtual_channel_bars.dart';
import 'bitacora_campo_screen.dart';
import 'client_map_screen.dart';
import 'client_search_screen.dart';
import 'gestor_activity_screen.dart';
import 'notifications_screen.dart';
import 'stats_screen.dart';
import 'tracking_screen.dart';
import 'etiquetas_admin_screen.dart';
import 'reassignment_screen.dart';
import 'cartera_upload_screen.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  final _campaignService = CampaignService();
  final _statsService = CampaignStatsService();
  final _firestoreService = FirestoreService();
  final _notificationService = NotificationService();

  bool _loading = true;
  String? _loadError;
  CampaignStats? _stats;
  Map<String, dynamic>? _campaignData;
  String? _campaignId;
  int _gestoresActivosCount = 0;
  int _pendingReturnsCount = 0;
  CampanaBancoFilterNotifier? _campanaFilterNotifier;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _loadData();
    });
  }

  @override
  void dispose() {
    _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);
    super.dispose();
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
    if (_loading) return;
    _statsService.clearCache();
    _loadData(forceRefresh: true);
  }

  Future<void> _loadData({bool forceRefresh = false}) async {
    if (forceRefresh) {
      _statsService.clearCache();
    }
    setState(() {
      _loading = true;
      _loadError = null;
    });

    try {
      // Timeout global: si Firestore web se cuelga (WebChannel bloqueado),
      // mostramos error con Reintentar en vez de spinner infinito.
      await _loadDataInner(forceRefresh: forceRefresh).timeout(
        const Duration(seconds: 60),
      );
    } catch (e, st) {
      debugPrint('AdminDashboard _loadData: $e\n$st');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _loadError = e.toString();
      });
    }
  }

  Future<void> _loadDataInner({bool forceRefresh = false}) async {
    try {
      final campaignId = await _campaignService
          .getActiveCampaignId()
          .timeout(const Duration(seconds: 20));
      if (campaignId == null) {
        if (mounted) setState(() => _loading = false);
        return;
      }
      if (!mounted) return;

      _campaignId = campaignId;
      _campaignData = await _campaignService
          .getCampaignData(campaignId)
          .timeout(const Duration(seconds: 20));

      final allClients = await _statsService
          .loadActiveClients(
            campaignId: campaignId,
          )
          .timeout(const Duration(seconds: 45));
      if (!mounted) return;
      context.read<CampanaBancoFilterNotifier>().updateAvailable(allClients);
      final campanaFilter =
          context.read<CampanaBancoFilterNotifier>().selected;

      final stats = await _statsService
          .loadForCampaign(
            campaignId: campaignId,
            campanaBancoFilter: campanaFilter,
            forceRefresh: forceRefresh,
          )
          .timeout(const Duration(seconds: 45));

      // Gestores y devoluciones en paralelo, cada uno con su timeout para
      // no bloquear el panel si una sola lectura se atasca.
      var pendingCount = 0;
      var gestoresLength = 0;
      try {
        final results = await Future.wait([
          _firestoreService
              .getGestoresActivos()
              .timeout(
                const Duration(seconds: 20),
                onTimeout: () => [],
              ),
          _firestoreService
              .listPendingReturns(campaignId)
              .timeout(
                const Duration(seconds: 20),
                onTimeout: () => [],
              ),
        ]);
        gestoresLength = (results[0] as List).length;
        pendingCount = (results[1] as List).length;
      } catch (e) {
        debugPrint('AdminDashboard gestores/pending: $e');
      }

      if (!mounted) return;
      setState(() {
        _stats = stats;
        _gestoresActivosCount = gestoresLength;
        _pendingReturnsCount = pendingCount;
        _loading = false;
      });
    } catch (e, st) {
      debugPrint('AdminDashboard _loadData: $e\n$st');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _loadError = e.toString();
      });
    }
  }

  void _openStatsTab(int tabIndex) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => StatsScreen(initialTab: tabIndex)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    final campanaFilterNotifier = context.watch<CampanaBancoFilterNotifier>();
    final stats = _stats;
    final campaignName =
        _campaignData?['nombre']?.toString() ?? _campaignId ?? 'Campaña';
    final diaCampana = _campaignData?['dia_campana']?.toString();
    final tramoActual = _campaignData?['tramo_actual']?.toString();

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Panel ejecutivo'),
            Text(
              campanaBancoFilterLabel(campanaFilterNotifier.selected),
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w400,
                color: Colors.white.withValues(alpha: 0.8),
              ),
            ),
          ],
        ),
        actions: [
          StreamBuilder<List<NotificationModel>>(
            stream: _notificationService.streamNotifications(
              auth.firebaseUser?.uid ?? '',
            ),
            builder: (context, snapshot) {
              final unread =
                  (snapshot.data ?? []).where((n) => !n.leida).length;
              return IconButton(
                icon: Badge(
                  isLabelVisible: unread > 0,
                  label: Text(unread > 9 ? '9+' : '$unread',
                      style: const TextStyle(fontSize: 10)),
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
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            tooltip: 'Actualizar',
            onPressed: () {
              _statsService.clearCache();
              _loadData(forceRefresh: true);
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const ClientSearchScreen()),
          );
        },
        icon: const Icon(Icons.search),
        label: const Text('Buscar cliente'),
        backgroundColor: AppTheme.primaryColor,
      ),
      body: Column(
        children: [
          CampanaBancoFilterBar(
            available: campanaFilterNotifier.available,
            selected: campanaFilterNotifier.selected,
            onSelected: campanaFilterNotifier.select,
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(
                      color: AppTheme.primaryColor,
                    ),
                  )
                : _loadError != null
                    ? _buildLoadError()
                    : stats == null || stats.total == 0
                    ? _buildEmpty()
                    : RefreshIndicator(
                        color: AppTheme.primaryColor,
                        onRefresh: () {
                          _statsService.clearCache();
                          return _loadData(forceRefresh: true);
                        },
                        child: SingleChildScrollView(
                          physics: const AlwaysScrollableScrollPhysics(),
                          padding: const EdgeInsets.fromLTRB(16, 12, 16, 88),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              _buildCampaignHeader(
                                campaignName,
                                diaCampana,
                                tramoActual,
                                stats,
                              ),
                              const SizedBox(height: 12),
                              CampaignKpiGrid(stats: stats, heroMode: true),
                              const SizedBox(height: 12),
                              Row(
                                children: [
                                  Expanded(
                                    child: StatCard(
                                      label: 'Pendientes',
                                      value: '${stats.total - stats.gestionados}',
                                      icon: Icons.pending_outlined,
                                      color: Colors.amber.shade700,
                                      small: true,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: StatCard(
                                      label: 'Gestores activos',
                                      value: '$_gestoresActivosCount',
                                      icon: Icons.groups_outlined,
                                      color: AppTheme.primaryColor,
                                      small: true,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              if (stats.campanaBancoBreakdown.length > 1)
                                CampanaBancoCards(
                                  entries: stats.campanaBancoBreakdown,
                                  selectedKey: campanaFilterNotifier.selected,
                                  onSelected: (key) {
                                    campanaFilterNotifier.select(key);
                                  },
                                ),
                              if (stats.campanaBancoBreakdown.length > 1)
                                const SizedBox(height: 16),
                              if (stats.contactMetrics != null) ...[
                                ContactResponseCard(
                                  metrics: stats.contactMetrics!,
                                  compact: true,
                                ),
                                const SizedBox(height: 12),
                                CanalSplitCard(metrics: stats.contactMetrics!),
                              ],
                              const SizedBox(height: 12),
                              TramoProgressBarFromStats(stats: stats),
                              const SizedBox(height: 12),
                              StatsFunnelCard(stats: stats, compact: true),
                              const SizedBox(height: 12),
                              GestorRankingPreview(
                                entries: stats.gestorRanking,
                                onViewAll: () => _openStatsTab(2),
                              ),
                              const SizedBox(height: 12),
                              _buildQuickActions(),
                            ],
                          ),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildCampaignHeader(
    String name,
    String? diaCampana,
    String? tramoActual,
    CampaignStats stats,
  ) {
    final subtitle = [
      if (diaCampana != null && diaCampana.isNotEmpty) 'Día $diaCampana',
      if (tramoActual != null && tramoActual.isNotEmpty) 'Tramo $tramoActual',
      'Día ${stats.diasTranscurridos} · ${stats.diasRestantes} restantes',
    ].join(' · ');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          name,
          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
        ),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
        const SizedBox(height: 4),
        Text(
          '${stats.total} cuentas · ${formatMoneyCompact(stats.deudaAsignada)} asignada',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
        ),
      ],
    );
  }

  Widget _buildQuickActions() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Accesos rápidos',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _actionChip(
                  Icons.upload_file,
                  'Cargar cartera',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const CarteraUploadScreen(),
                      ),
                    );
                  },
                ),
                _actionChip(
                  Icons.swap_horiz,
                  _pendingReturnsCount > 0
                      ? 'Reasignar ($_pendingReturnsCount)'
                      : 'Reasignar',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const ReassignmentScreen(),
                      ),
                    );
                  },
                ),
                _actionChip(
                  Icons.bar_chart,
                  'Estadísticas',
                  () => _openStatsTab(0),
                ),
                _actionChip(
                  Icons.timeline,
                  'Actividad',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const GestorActivityScreen(),
                      ),
                    );
                  },
                ),
                _actionChip(
                  Icons.menu_book_outlined,
                  'Bitácora',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const BitacoraCampoScreen(),
                      ),
                    );
                  },
                ),
                _actionChip(
                  Icons.groups,
                  'Equipo GPS',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const TrackingScreen()),
                    );
                  },
                ),
                _actionChip(
                  Icons.map,
                  'Mapa',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const ClientMapScreen(),
                      ),
                    );
                  },
                ),
                _actionChip(
                  Icons.search,
                  'Buscar cliente',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const ClientSearchScreen(),
                      ),
                    );
                  },
                ),
                _actionChip(
                  Icons.label_outline,
                  'Etiquetas',
                  () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const EtiquetasAdminScreen(),
                      ),
                    );
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionChip(IconData icon, String label, VoidCallback onTap) {
    return ActionChip(
      avatar: Icon(icon, size: 18, color: AppTheme.primaryColor),
      label: Text(label),
      onPressed: onTap,
    );
  }

  Widget _buildLoadError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.cloud_off_outlined,
                size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(
              'No se pudo cargar el panel',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'La conexión con Firestore se cortó al leer la cartera. '
              'Vuelve a intentar.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade600, height: 1.35),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => _loadData(forceRefresh: true),
              icon: const Icon(Icons.refresh),
              label: const Text('Reintentar'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.dashboard_outlined,
                size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(
              'No hay datos de campaña',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Carga el Excel del banco para publicar la cartera a los gestores.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade600, height: 1.35),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const CarteraUploadScreen(),
                  ),
                );
              },
              icon: const Icon(Icons.upload_file),
              label: const Text('Cargar cartera'),
            ),
          ],
        ),
      ),
    );
  }
}
