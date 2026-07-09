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
import 'client_map_screen.dart';
import 'client_search_screen.dart';
import 'notifications_screen.dart';
import 'stats_screen.dart';
import 'tracking_screen.dart';
import 'etiquetas_admin_screen.dart';
import 'reassignment_screen.dart';

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
    setState(() => _loading = true);

    final campaignId = await _campaignService.getActiveCampaignId();
    if (campaignId == null) {
      if (mounted) setState(() => _loading = false);
      return;
    }
    if (!mounted) return;

    _campaignId = campaignId;
    _campaignData = await _campaignService.getCampaignData(campaignId);

    final allClients = await _statsService.loadActiveClients(
      campaignId: campaignId,
    );
    if (mounted) {
      context.read<CampanaBancoFilterNotifier>().updateAvailable(allClients);
    }

    final campanaFilter =
        context.read<CampanaBancoFilterNotifier>().selected;

    final stats = await _statsService.loadForCampaign(
      campaignId: campaignId,
      campanaBancoFilter: campanaFilter,
      forceRefresh: forceRefresh,
    );

    final gestores = await _firestoreService.getGestoresActivos();
    final pendingReturns = await _firestoreService.listPendingReturns(campaignId);

    if (!mounted) return;
    setState(() {
      _stats = stats;
      _gestoresActivosCount = gestores.length;
      _pendingReturnsCount = pendingReturns.length;
      _loading = false;
    });
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
          ],
        ),
      ),
    );
  }
}
