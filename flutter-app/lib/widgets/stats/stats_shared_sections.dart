import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../config/theme.dart';
import '../../models/campaign_stats.dart';
import '../../models/client_model.dart';
import '../../utils/responsive.dart';
import '../../utils/stats_format.dart';
import '../stat_card.dart';
import 'stats_gauge_card.dart';
import 'stats_pie_chart.dart';

class StatsGaugeRow extends StatelessWidget {
  final CampaignStats stats;

  const StatsGaugeRow({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= ResponsiveBreakpoints.expanded
            ? 3
            : constraints.maxWidth >= ResponsiveBreakpoints.compact
                ? 2
                : 1;
        final gauges = [
          StatsGaugeCard(
            label: 'AVANCE GESTIÓN',
            value: stats.avancePct,
            color: Colors.indigo,
            subtitle: '${stats.gestionados} de ${stats.total}',
          ),
          StatsGaugeCard(
            label: 'RECUP. BANCO',
            value: stats.tasaRecuperacionBanco,
            color: Colors.teal,
            subtitle: formatMoneyCompact(stats.recuperadoBanco),
          ),
          StatsGaugeCard(
            label: 'COBERTURA GPS',
            value: stats.gpsPct,
            color: Colors.deepPurple,
            subtitle: '${stats.geolocated} geoloc.',
          ),
        ];

        if (columns == 1) {
          return Column(
            children: gauges
                .map((g) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: g,
                    ))
                .toList(),
          ).animate().fadeIn(duration: 400.ms);
        }

        return Row(
          children: gauges
              .map((g) => Expanded(child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: g,
                  )))
              .toList(),
        ).animate().fadeIn(duration: 400.ms);
      },
    );
  }
}

class CampaignKpiGrid extends StatelessWidget {
  final CampaignStats stats;
  final bool compact;
  final bool heroMode;

  const CampaignKpiGrid({
    super.key,
    required this.stats,
    this.compact = false,
    this.heroMode = false,
  });

  @override
  Widget build(BuildContext context) {
    if (heroMode) {
      return Column(
        children: [
          Row(
            children: [
              Expanded(
                child: StatCard(
                  label: 'Recup. banco',
                  value: '${stats.tasaRecuperacionBanco.toStringAsFixed(1)}%',
                  icon: Icons.savings_outlined,
                  color: Colors.teal,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: StatCard(
                  label: 'Recuperado',
                  value: formatMoneyCompact(stats.recuperadoBanco),
                  icon: Icons.account_balance,
                  color: AppTheme.accentColor,
                  small: true,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: StatCard(
                  label: 'Avance',
                  value: '${stats.avancePct.toStringAsFixed(0)}%',
                  icon: Icons.trending_up,
                  color: AppTheme.primaryColor,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: StatCard(
                  label: 'Promesas',
                  value: '${stats.promesasCount}',
                  icon: Icons.handshake_outlined,
                  color: Colors.blueGrey,
                  small: true,
                ),
              ),
            ],
          ),
        ],
      );
    }

    final cards = [
      StatCard(
        label: 'Total',
        value: '${stats.total}',
        icon: Icons.people_outline,
        color: AppTheme.primaryColor,
      ),
      StatCard(
        label: 'Habidos',
        value: '${stats.statusCounts['visitado_habido'] ?? 0}',
        icon: Icons.check_circle_outline,
        color: Colors.green.shade600,
      ),
      StatCard(
        label: 'Deuda',
        value: formatMoneyCompact(stats.deudaAsignada),
        icon: Icons.account_balance_wallet_outlined,
        color: AppTheme.accentColor,
        small: true,
      ),
      if (!compact) ...[
        StatCard(
          label: 'Recup. banco',
          value: formatMoneyCompact(stats.recuperadoBanco),
          icon: Icons.savings_outlined,
          color: Colors.teal,
          small: true,
        ),
        StatCard(
          label: 'Promesas',
          value: formatMoneyCompact(stats.montoPrometido),
          icon: Icons.handshake_outlined,
          color: Colors.blueGrey,
          small: true,
        ),
      ],
    ];

    if (compact) {
      return LayoutBuilder(
        builder: (context, constraints) {
          final itemWidth = constraints.maxWidth >= ResponsiveBreakpoints.expanded
              ? 200.0
              : 160.0;
          return Wrap(
            spacing: 8,
            runSpacing: 8,
            children: cards
                .map((c) => SizedBox(width: itemWidth, child: c))
                .toList(),
          );
        },
      );
    }

    return Column(
      children: [
        Row(
          children: [
            Expanded(child: cards[0]),
            const SizedBox(width: 8),
            Expanded(child: cards[1]),
            const SizedBox(width: 8),
            Expanded(child: cards[2]),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(child: cards[3]),
            const SizedBox(width: 8),
            Expanded(child: cards[4]),
          ],
        ),
      ],
    );
  }
}

class StatsGlobalProgress extends StatelessWidget {
  final CampaignStats stats;

  const StatsGlobalProgress({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    final pct = stats.total > 0 ? stats.gestionados / stats.total : 0.0;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Progreso Global',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                ),
                Text(
                  '${stats.gestionados} / ${stats.total}',
                  style: TextStyle(color: Colors.grey.shade600),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: pct,
                minHeight: 12,
                backgroundColor: Colors.grey.shade200,
                valueColor:
                    const AlwaysStoppedAnimation<Color>(AppTheme.primaryColor),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '${formatPct(pct * 100)} completado',
              style: TextStyle(color: Colors.grey.shade500, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class StatsFunnelCard extends StatelessWidget {
  final CampaignStats stats;
  final bool compact;

  const StatsFunnelCard({
    super.key,
    required this.stats,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    if (stats.funnelStages.isEmpty) return const SizedBox.shrink();
    final max = stats.funnelStages.map((e) => e.value).reduce(math.max);

    return Card(
      child: Padding(
        padding: EdgeInsets.all(compact ? 12 : 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Embudo de gestión',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: compact ? 14 : 15,
              ),
            ),
            const SizedBox(height: 12),
            ...stats.funnelStages.map((stage) {
              final w = max > 0 ? stage.value / max : 0.0;
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: compact ? 100 : 120,
                      child: Text(
                        stage.label,
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                    Expanded(
                      flex: (w * 100).round().clamp(1, 100),
                      child: Container(
                        height: compact ? 22 : 28,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryColor
                              .withValues(alpha: 0.2 + w * 0.6),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 8),
                        child: Text(
                          '${stage.value}',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
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
}

class StatsPieChartCard extends StatelessWidget {
  final CampaignStats stats;

  const StatsPieChartCard({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    final counts = stats.statusCounts;
    final entries = [
      StatsPieEntry(
        'Pendiente',
        counts['pendiente'] ?? 0,
        AppTheme.statusPendiente,
      ),
      StatsPieEntry(
        'Habido',
        counts['visitado_habido'] ?? 0,
        AppTheme.statusVisitadoHabido,
      ),
      StatsPieEntry(
        'No Habido',
        counts['visitado_no_habido'] ?? 0,
        AppTheme.statusVisitadoNoHabido,
      ),
      StatsPieEntry(
        'Inubicable',
        counts['fallecido_inubicable'] ?? 0,
        AppTheme.statusFallecido,
      ),
      StatsPieEntry(
        'Suplantación',
        counts['suplantacion'] ?? 0,
        AppTheme.statusSuplantacion,
      ),
      StatsPieEntry(
        'Pago No Reg.',
        counts['pago_no_registrado'] ?? 0,
        AppTheme.statusPagoNoRegistrado,
      ),
    ];

    if (entries.every((e) => e.value == 0)) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Distribución por Estado',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 16),
            Center(
              child: StatsPieChart(entries: entries, total: stats.total),
            ),
          ],
        ),
      ),
    );
  }
}

class StatsTramoBarsCard extends StatelessWidget {
  final CampaignStats stats;

  const StatsTramoBarsCard({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    if (stats.tramoCounts.isEmpty) return const SizedBox.shrink();
    final max = stats.tramoCounts.values.fold<int>(0, math.max);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Clientes por tramo',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            ...stats.tramoCounts.entries.map((e) {
              final label = e.key == 0 ? 'Sin tramo' : 'Tramo ${e.key}';
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: 72,
                      child: Text(label, style: const TextStyle(fontSize: 12)),
                    ),
                    Expanded(
                      child: LinearProgressIndicator(
                        value: max > 0 ? e.value / max : 0,
                        minHeight: 10,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: const AlwaysStoppedAnimation<Color>(
                          AppTheme.primaryColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text('${e.value}', style: const TextStyle(fontSize: 12)),
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

/// Tramo chips bar (E1/E2/E3) from client list — used in gestor dashboard.
class TramoProgressBar extends StatelessWidget {
  final List<ClientModel> clients;

  const TramoProgressBar({super.key, required this.clients});

  @override
  Widget build(BuildContext context) {
    final active = clients.where((c) => c.isActiveForGestor).toList();
    final e1 = active.where((c) => c.tramoActual == 1).length;
    final e2 = active.where((c) => c.tramoActual == 2).length;
    final e3 = active.where((c) => c.tramoActual == 3).length;
    final especial = active.where((c) => c.isGestionEspecialSection).length;
    final total = active.length;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryColor.withValues(alpha: 0.08),
            AppTheme.accentColor.withValues(alpha: 0.06),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: AppTheme.primaryColor.withValues(alpha: 0.15),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Cartera por etapa (ciclo 59 días/cuenta)',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  color: AppTheme.textPrimary,
                ),
              ),
              Text(
                '$total activas',
                style: TextStyle(
                  color: Colors.grey.shade700,
                  fontWeight: FontWeight.w500,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _etapaChip('E1', e1, AppTheme.primaryColor),
              const SizedBox(width: 8),
              _etapaChip('E2', e2, AppTheme.accentColor),
              const SizedBox(width: 8),
              _etapaChip('E3', e3, AppTheme.warning),
              if (especial > 0) ...[
                const SizedBox(width: 8),
                _etapaChip('Esp.', especial, AppTheme.warning),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _etapaChip(String label, int count, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.25)),
        ),
        child: Column(
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
            Text(
              '$count',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Compact tramo bar for admin hub using aggregated tramo counts.
class TramoProgressBarFromStats extends StatelessWidget {
  final CampaignStats stats;

  const TramoProgressBarFromStats({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    final e1 = stats.tramoCounts[1] ?? 0;
    final e2 = stats.tramoCounts[2] ?? 0;
    final e3 = stats.tramoCounts[3] ?? 0;
    final total = stats.total;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Cartera por etapa',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                ),
                Text(
                  '$total cuentas',
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                _chip('E1', e1, AppTheme.primaryColor),
                const SizedBox(width: 8),
                _chip('E2', e2, AppTheme.accentColor),
                const SizedBox(width: 8),
                _chip('E3', e3, AppTheme.warning),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, int count, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Text(label, style: TextStyle(fontSize: 11, color: color)),
            Text(
              '$count',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
