import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/campaign_stats.dart';
import '../services/auth_service.dart';
import '../services/campana_banco_filter_notifier.dart';
import '../services/campaign_service.dart';
import '../services/campaign_stats_service.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/stats_format.dart';
import '../widgets/campana_banco_filter_bar.dart';
import '../widgets/stats/stats_ranking_list.dart';
import '../widgets/stats/stats_shared_sections.dart';
import '../widgets/stats/stats_pie_chart.dart';
import '../widgets/stats/contact_response_card.dart';
import '../widgets/stats/virtual_channel_bars.dart';

class StatsScreen extends StatefulWidget {
  final int initialTab;

  const StatsScreen({super.key, this.initialTab = 0});

  @override
  State<StatsScreen> createState() => _StatsScreenState();
}

class _StatsScreenState extends State<StatsScreen>
    with SingleTickerProviderStateMixin {
  final _campaignService = CampaignService();
  final _statsService = CampaignStatsService();

  bool _loading = true;
  CampaignStats? _stats;
  bool _isExecutiveView = false;
  TabController? _tabController;
  CampanaBancoFilterNotifier? _campanaFilterNotifier;

  @override
  void dispose() {
    _campanaFilterNotifier?.removeListener(_onCampanaFilterChanged);
    _tabController?.dispose();
    super.dispose();
  }

  Future<void> _loadStats({bool forceRefresh = false}) async {
    setState(() => _loading = true);

    final campaignId = await _campaignService.getActiveCampaignId();
    if (campaignId == null) {
      if (mounted) setState(() => _loading = false);
      return;
    }
    if (!mounted) return;

    final auth = context.read<AuthService>();
    final profile = auth.profile;
    List<String>? sectionFilter;

    if (profile?.isGestor ?? false) {
      sectionFilter = <String>{
        ...(profile?.secciones ?? const <String>[]),
        if ((profile?.seccion ?? '').isNotEmpty) profile!.seccion,
      }.toList()
        ..sort();
    }

    final allClients = await _statsService.loadActiveClients(
      campaignId: campaignId,
      sectionFilter: sectionFilter,
    );
    if (mounted) {
      context.read<CampanaBancoFilterNotifier>().updateAvailable(allClients);
    }

    final campanaFilter =
        context.read<CampanaBancoFilterNotifier>().selected;

    final stats = await _statsService.loadForCampaign(
      campaignId: campaignId,
      sectionFilter: sectionFilter,
      campanaBancoFilter: campanaFilter,
      forceRefresh: forceRefresh,
    );

    if (!mounted) return;

    final executive = profile != null &&
        profile.canViewStats &&
        !profile.isGestor;

    TabController? tabs = _tabController;
    if (executive && (tabs == null || tabs.length != 4)) {
      tabs?.dispose();
      tabs = TabController(
        length: 4,
        vsync: this,
        initialIndex: widget.initialTab.clamp(0, 3),
      );
    } else if (!executive && tabs != null) {
      tabs.dispose();
      tabs = null;
    }

    setState(() {
      _stats = stats;
      _isExecutiveView = executive;
      _tabController = tabs;
      _loading = false;
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _loadStats();
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
    if (_loading) return;
    _statsService.clearCache();
    _loadStats(forceRefresh: true);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    final profile = auth.profile;
    final campanaFilterNotifier = context.watch<CampanaBancoFilterNotifier>();

    if (profile == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Estadísticas')),
        body: const Center(child: Text('Cargando perfil...')),
      );
    }

    final title = profile.isGestor ? 'Mis estadísticas' : 'Estadísticas';

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title),
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
        bottom: _isExecutiveView && _tabController != null
            ? TabBar(
                controller: _tabController,
                isScrollable: true,
                labelColor: Colors.white,
                unselectedLabelColor: Colors.white70,
                indicatorColor: Colors.white,
                tabs: const [
                  Tab(text: 'Resumen'),
                  Tab(text: 'Finanzas'),
                  Tab(text: 'Equipo'),
                  Tab(text: 'Territorio'),
                ],
              )
            : null,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: () {
              _statsService.clearCache();
              _loadStats(forceRefresh: true);
            },
          ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          CampanaBancoFilterBar(
            available: campanaFilterNotifier.available,
            selected: campanaFilterNotifier.selected,
            onSelected: (value) {
              campanaFilterNotifier.select(value);
            },
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(
                      color: AppTheme.primaryColor,
                    ),
                  )
                : _stats == null || _stats!.total == 0
                    ? _buildEmpty()
                    : _isExecutiveView && _tabController != null
                        ? TabBarView(
                            controller: _tabController,
                            children: [
                              _buildScroll(
                                _buildResumenTab(_stats!, showGanancia: true),
                              ),
                              _buildScroll(_buildFinanzasTab(_stats!)),
                              _buildScroll(_buildEquipoTab(_stats!)),
                              _buildScroll(_buildTerritorioTab(_stats!)),
                            ],
                          )
                        : _buildScroll(
                            _buildGestorSummary(
                              _stats!,
                              showGanancia: false,
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildScroll(Widget child) {
    return RefreshIndicator(
      onRefresh: () => _loadStats(forceRefresh: true),
      color: AppTheme.primaryColor,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: child,
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
            Icon(Icons.bar_chart, size: 48, color: Colors.grey.shade400),
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

  Widget _buildGestorSummary(CampaignStats s, {required bool showGanancia}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        StatsGaugeRow(stats: s),
        const SizedBox(height: 12),
        CampaignKpiGrid(stats: s, compact: true),
        const SizedBox(height: 16),
        _buildFinancialSummary(s, showGanancia: showGanancia),
        const SizedBox(height: 16),
        StatsPieChartCard(stats: s),
        const SizedBox(height: 16),
        _buildSectionBars(s),
      ],
    );
  }

  Widget _buildResumenTab(CampaignStats s, {required bool showGanancia}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        StatsGaugeRow(stats: s),
        const SizedBox(height: 12),
        CampaignKpiGrid(stats: s),
        const SizedBox(height: 16),
        StatsGlobalProgress(stats: s),
        const SizedBox(height: 16),
        StatsPieChartCard(stats: s),
        const SizedBox(height: 16),
        if (s.contactMetrics != null) ...[
          ContactResponseCard(metrics: s.contactMetrics!),
          const SizedBox(height: 16),
          VirtualChannelBars(metrics: s.contactMetrics!),
          const SizedBox(height: 16),
          CanalSplitCard(metrics: s.contactMetrics!),
          const SizedBox(height: 16),
        ],
        StatsFunnelCard(stats: s),
      ],
    );
  }

  Widget _buildFinanzasTab(CampaignStats s) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildFinancialSummary(s, showGanancia: true),
        const SizedBox(height: 16),
        _buildProjectionCards(s),
        const SizedBox(height: 16),
        _buildDebtDonutCard(s),
        const SizedBox(height: 16),
        StatsTramoBarsCard(stats: s),
      ],
    );
  }

  Widget _buildEquipoTab(CampaignStats s) {
    return StatsRankingList(entries: s.gestorRanking);
  }

  Widget _buildTerritorioTab(CampaignStats s) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildSectionTable(s),
        const SizedBox(height: 16),
        _buildHorizontalBars(
          title: 'Top departamentos (cuentas)',
          items: s.topDepartmentsByCount,
          showDeuda: false,
        ),
        const SizedBox(height: 16),
        _buildHorizontalBars(
          title: 'Top departamentos (deuda)',
          items: s.topDepartmentsByDeuda,
          showDeuda: true,
        ),
        const SizedBox(height: 16),
        _buildHorizontalBars(
          title: 'Top distritos (deuda)',
          items: s.topDistrictsByDeuda,
          showDeuda: true,
        ),
      ],
    );
  }

  Widget _buildDebtDonutCard(CampaignStats s) {
    final sinGestionar =
        (s.deudaAsignada - s.deudaGestionada).clamp(0.0, double.infinity);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Cobertura de deuda en campo',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            Center(
              child: StatsPieChart(
                entries: [
                  StatsPieEntry(
                    'Gestionada',
                    s.deudaGestionada.toInt(),
                    AppTheme.primaryColor,
                  ),
                  StatsPieEntry(
                    'Sin gestionar',
                    sinGestionar.toInt(),
                    Colors.grey.shade300,
                  ),
                ],
                total: (s.deudaGestionada + sinGestionar).toInt(),
                size: 160,
                showLegend: true,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFinancialSummary(CampaignStats s, {required bool showGanancia}) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Recuperación y cartera',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            _moneyRow('Deuda asignada (banco)', s.deudaAsignada),
            _moneyRow('Deuda pendiente (banco)', s.deudaPendiente),
            _moneyRow(
              'Recuperado según banco',
              s.recuperadoBanco,
              highlight: Colors.green.shade700,
              subtitle: 'Asignada − pendiente (datos Excel)',
            ),
            _moneyRow('Deuda gestionada en campo', s.deudaGestionada,
                subtitle: 'Clientes ya visitados'),
            _moneyRow('Monto en promesas', s.montoPrometido,
                subtitle: '${s.promesasCount} compromisos'),
            if (showGanancia) ...[
              const Divider(height: 20),
              _moneyRow(
                'Ganancia estimada (${formatPct(s.porcentajeComisionJefe, decimals: 0)})',
                s.gananciaJefe,
                highlight: AppTheme.primaryColor,
                subtitle: 'Sobre recuperación según banco',
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _moneyRow(
    String label,
    double value, {
    Color? highlight,
    String? subtitle,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(label, style: const TextStyle(fontSize: 13)),
              ),
              Text(
                formatMoneyFull(value),
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                  color: highlight,
                ),
              ),
            ],
          ),
          if (subtitle != null)
            Text(
              subtitle,
              style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
            ),
        ],
      ),
    );
  }

  Widget _buildProjectionCards(CampaignStats s) {
    return Column(
      children: [
        Card(
          color: Colors.blue.shade50,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Proyección lineal (ritmo de campaña)',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                ),
                const SizedBox(height: 8),
                Text(
                  formatMoneyFull(s.proyeccionLineal),
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.primaryColor,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Día ${s.diasTranscurridos} · ${s.diasRestantes} días restantes · '
                  'Ritmo ${formatMoneyCompact(s.ritmoDiarioRecuperacion)}/día',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Card(
          color: Colors.teal.shade50,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Proyección con promesas',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                ),
                const SizedBox(height: 4),
                Text(
                  'Escenario si se cumplen los compromisos registrados',
                  style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
                ),
                const SizedBox(height: 8),
                Text(
                  formatMoneyFull(s.proyeccionPromesas),
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Colors.teal.shade800,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSectionBars(CampaignStats s) {
    if (s.sectionStats.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Avance por Sección',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            ...s.sectionStats.map((sec) {
              final pct = sec.avancePct / 100;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            'Sección ${sec.seccion}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w500,
                              fontSize: 13,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Text(
                          '${sec.visitados}/${sec.total} (${sec.avancePct.toStringAsFixed(0)}%)',
                          style: TextStyle(
                            color: Colors.grey.shade600,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: pct,
                        minHeight: 8,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          Color.lerp(Colors.red, Colors.green, pct) ??
                              AppTheme.primaryColor,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTable(CampaignStats s) {
    return Card(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          headingRowHeight: 36,
          dataRowMinHeight: 32,
          columns: const [
            DataColumn(label: Text('Sección', style: TextStyle(fontSize: 11))),
            DataColumn(label: Text('Clientes', style: TextStyle(fontSize: 11))),
            DataColumn(label: Text('Avance', style: TextStyle(fontSize: 11))),
            DataColumn(label: Text('Deuda', style: TextStyle(fontSize: 11))),
            DataColumn(label: Text('Recup.', style: TextStyle(fontSize: 11))),
          ],
          rows: s.sectionStats.map((sec) {
            return DataRow(cells: [
              DataCell(Text(sec.seccion, style: const TextStyle(fontSize: 11))),
              DataCell(Text('${sec.total}', style: const TextStyle(fontSize: 11))),
              DataCell(Text('${sec.avancePct.toStringAsFixed(0)}%',
                  style: const TextStyle(fontSize: 11))),
              DataCell(Text(formatMoneyCompact(sec.deuda),
                  style: const TextStyle(fontSize: 11))),
              DataCell(Text(formatMoneyCompact(sec.recuperadoBanco),
                  style: const TextStyle(fontSize: 11))),
            ]);
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildHorizontalBars({
    required String title,
    required List<StatsBarItem> items,
    required bool showDeuda,
  }) {
    if (items.isEmpty) return const SizedBox.shrink();
    final maxVal = items.first.value;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
            const SizedBox(height: 12),
            ...items.map((e) {
              final display = showDeuda
                  ? formatMoneyCompact(e.value)
                  : '${e.count}';
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: 90,
                      child: Text(
                        e.label,
                        style: const TextStyle(fontSize: 12),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: LinearProgressIndicator(
                          value: maxVal > 0 ? e.value / maxVal : 0,
                          minHeight: 14,
                          backgroundColor: Colors.grey.shade100,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            AppTheme.primaryColor.withValues(alpha: 0.7),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(display,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600, fontSize: 12)),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
