import 'package:flutter/material.dart';

import '../../config/theme.dart';
import '../../models/contact_metrics.dart';
import '../../utils/stats_format.dart';
import 'stats_pie_chart.dart';

class ContactResponseCard extends StatelessWidget {
  final ContactMetrics metrics;
  final bool compact;

  const ContactResponseCard({
    super.key,
    required this.metrics,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final entries = [
      StatsPieEntry(
        'Efectivo',
        metrics.contactoEfectivo,
        Colors.green.shade600,
      ),
      StatsPieEntry(
        'No efectivo',
        metrics.contactoNoEfectivo,
        Colors.orange.shade600,
      ),
      StatsPieEntry(
        'No contacto',
        metrics.noContacto,
        Colors.red.shade400,
      ),
      StatsPieEntry(
        'Pendiente',
        metrics.pendientes,
        AppTheme.statusPendiente,
      ),
    ];

    return Card(
      child: Padding(
        padding: EdgeInsets.all(compact ? 12 : 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Respuesta de contacto',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 4),
            Text(
              'Cobertura y contacto — no confirma pagos del banco',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (!compact)
                  Expanded(
                    child: StatsPieChart(
                      entries: entries,
                      total: metrics.total,
                      size: 140,
                      showLegend: false,
                    ),
                  ),
                Expanded(
                  flex: compact ? 1 : 1,
                  child: Column(
                    children: [
                      _metricRow(
                        'Contacto efectivo',
                        formatPct(metrics.pctContactoEfectivo),
                        '${metrics.contactoEfectivo} / ${metrics.totalGestionados} gest.',
                      ),
                      _metricRow(
                        'Respuesta TEL',
                        formatPct(metrics.pctRespuestaTel),
                        '${metrics.contactoEfectivoTel} / ${metrics.canalTel} por tel.',
                      ),
                      _metricRow(
                        'Seguimiento virtual',
                        formatPct(metrics.pctVirtualSeguimiento),
                        '${metrics.virtualConRespuesta} / ${metrics.virtualEnviados} SMS/WSP',
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _metricRow(String label, String value, String subtitle) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(fontSize: 12)),
                Text(
                  subtitle,
                  style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
                ),
              ],
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 14,
              color: AppTheme.primaryColor,
            ),
          ),
        ],
      ),
    );
  }
}
