import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../models/gestor_stats.dart';
import '../utils/section_utils.dart';
import 'stat_card.dart';

/// Panel de avance y KPIs para el perfil del gestor de campo.
class GestorProfileStatsPanel extends StatelessWidget {
  final GestorStats stats;
  final bool loading;
  final String? errorMessage;
  final VoidCallback? onRefresh;
  final VoidCallback? onViewFullStats;

  const GestorProfileStatsPanel({
    super.key,
    required this.stats,
    this.loading = false,
    this.errorMessage,
    this.onRefresh,
    this.onViewFullStats,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Mi avance en campaña',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
                  ),
                ),
                if (onRefresh != null)
                  IconButton(
                    icon: loading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh, size: 20),
                    tooltip: 'Actualizar estadísticas',
                    onPressed: loading ? null : onRefresh,
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
            if (errorMessage != null) ...[
              const SizedBox(height: 8),
              Text(
                errorMessage!,
                style: TextStyle(color: Colors.orange.shade800, fontSize: 12),
              ),
            ],
            const SizedBox(height: 10),
            _buildProgress(context),
            const SizedBox(height: 12),
            _buildKpiGrid(),
            if (stats.rutaHoyTotal != null && stats.rutaHoyTotal! > 0) ...[
              const SizedBox(height: 12),
              _buildRutaHoy(),
            ],
            if (stats.porSeccion.length > 1) ...[
              const SizedBox(height: 14),
              _buildSectionBreakdown(),
            ],
            if (_statusEntries.isNotEmpty) ...[
              const SizedBox(height: 14),
              _buildStatusChips(),
            ],
            if (onViewFullStats != null) ...[
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: onViewFullStats,
                  icon: const Icon(Icons.bar_chart_outlined, size: 18),
                  label: const Text('Ver estadísticas completas'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildProgress(BuildContext context) {
    final pct = stats.avancePct / 100;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '${stats.avancePct.toStringAsFixed(1)}% completado',
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
            ),
            Text(
              '${stats.visitados} / ${stats.total}',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: stats.total > 0 ? pct.clamp(0.0, 1.0) : 0,
            minHeight: 10,
            backgroundColor: Colors.grey.shade200,
            valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.primaryColor),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          '${stats.visitados} gestionados · ${stats.pendientes} pendientes · '
          '${stats.gestionesHoy} hoy',
          style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
        ),
      ],
    );
  }

  Widget _buildKpiGrid() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: StatCard(
                label: 'Clientes',
                value: '${stats.total}',
                icon: Icons.people_outline,
                color: AppTheme.primaryColor,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: StatCard(
                label: 'Pendientes',
                value: '${stats.pendientes}',
                icon: Icons.hourglass_empty,
                color: AppTheme.warning,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: StatCard(
                label: 'Hoy',
                value: '${stats.gestionesHoy}',
                icon: Icons.today_outlined,
                color: AppTheme.success,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: StatCard(
                label: 'Habidos',
                value: '${stats.habidos}',
                icon: Icons.check_circle_outline,
                color: AppTheme.statusHabido,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: StatCard(
                label: 'Recup. banco',
                value: _formatMoney(stats.recuperadoBanco),
                icon: Icons.savings_outlined,
                color: Colors.teal,
                small: true,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: StatCard(
                label: 'Deuda gest.',
                value: _formatMoney(stats.deudaGestionada),
                icon: Icons.payments_outlined,
                color: AppTheme.accentColor,
                small: true,
              ),
            ),
          ],
        ),
        if (stats.promesasCount > 0) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: StatCard(
                  label: 'Promesas',
                  value: '${stats.promesasCount}',
                  icon: Icons.handshake_outlined,
                  color: Colors.blueGrey,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                flex: 2,
                child: StatCard(
                  label: 'Monto prometido',
                  value: _formatMoney(stats.montoPrometido),
                  icon: Icons.attach_money,
                  color: Colors.teal.shade700,
                  small: true,
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildRutaHoy() {
    final total = stats.rutaHoyTotal ?? 0;
    final done = stats.rutaHoyCompletados ?? 0;
    final pct = stats.rutaHoyAvancePct ?? 0;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.primaryLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Ruta de hoy',
            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$done de $total visitas en ruta',
                style: TextStyle(color: Colors.grey.shade700, fontSize: 12),
              ),
              Text(
                '${pct.toStringAsFixed(0)}%',
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  color: AppTheme.primaryColor,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: total > 0 ? (done / total).clamp(0.0, 1.0) : 0,
              minHeight: 6,
              backgroundColor: Colors.white,
              valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.accent),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionBreakdown() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Avance por sección',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        const SizedBox(height: 8),
        ...stats.porSeccion.map((s) {
          final pct = s.total > 0 ? s.visitados / s.total : 0.0;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        sectionDisplayLabel(s.sectionKey),
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Text(
                      '${s.visitados}/${s.total}',
                      style: TextStyle(color: Colors.grey.shade600, fontSize: 11),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: pct,
                    minHeight: 6,
                    backgroundColor: Colors.grey.shade200,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      Color.lerp(Colors.red, Colors.green, pct) ?? AppTheme.primary,
                    ),
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  List<({String key, int count, String label})> get _statusEntries {
    const labels = <String, String>{
      'pendiente': 'Pendiente',
      'visitado_habido': 'Habido',
      'visitado_no_habido': 'No habido',
      'fallecido_inubicable': 'Inubicable',
      'suplantacion': 'Suplantación',
      'pago_no_registrado': 'Pago no reg.',
    };
    return stats.porEstado.entries
        .where((e) => e.value > 0)
        .map((e) => (
              key: e.key,
              count: e.value,
              label: labels[e.key] ?? e.key,
            ))
        .toList()
      ..sort((a, b) => b.count.compareTo(a.count));
  }

  Widget _buildStatusChips() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Por estado de gestión',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: _statusEntries.map((e) {
            final color = AppTheme.getStatusColor(e.key);
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: color.withValues(alpha: 0.35)),
              ),
              child: Text(
                '${e.label}: ${e.count}',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: color.withValues(alpha: 0.95),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  String _formatMoney(double value) {
    if (value >= 1000000) return 'S/${(value / 1000000).toStringAsFixed(1)}M';
    if (value >= 1000) return 'S/${(value / 1000).toStringAsFixed(1)}K';
    return 'S/${value.toStringAsFixed(0)}';
  }
}
