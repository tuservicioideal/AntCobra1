import 'package:flutter/material.dart';

import '../../config/theme.dart';
import '../../models/contact_metrics.dart';

class VirtualChannelBars extends StatelessWidget {
  final ContactMetrics metrics;

  const VirtualChannelBars({super.key, required this.metrics});

  @override
  Widget build(BuildContext context) {
    final items = [
      ('SMS enviados', metrics.smsEnviados, Colors.blue),
      ('WSP enviados', metrics.wspEnviados, Colors.green),
      ('Mailing', metrics.mailingEnviados, Colors.indigo),
      ('Llamada sin respuesta', metrics.llamadaSinRespuesta, Colors.orange),
    ];
    final max = items.map((e) => e.$2).fold(0, (a, b) => a > b ? a : b);

    if (max == 0) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Canales virtuales y llamadas',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            ...items.map((item) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: 130,
                      child: Text(item.$1, style: const TextStyle(fontSize: 12)),
                    ),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: LinearProgressIndicator(
                          value: max > 0 ? item.$2 / max : 0,
                          minHeight: 14,
                          backgroundColor: Colors.grey.shade100,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(item.$3),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${item.$2}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
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

class CanalSplitCard extends StatelessWidget {
  final ContactMetrics metrics;

  const CanalSplitCard({super.key, required this.metrics});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Gestión por canal',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _canalTile(
                    'Call center (TEL)',
                    metrics.canalTel,
                    metrics.pctCanalTel,
                    Icons.headset_mic,
                    Colors.teal,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _canalTile(
                    'Campo (CAM)',
                    metrics.canalCam,
                    metrics.pctCanalCam,
                    Icons.directions_walk,
                    AppTheme.primaryColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Promesas TEL: ${metrics.promesasTel} · CAM: ${metrics.promesasCam}',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _canalTile(
    String label,
    int count,
    double pct,
    IconData icon,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 6),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500),
          ),
          Text(
            '$count',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            '${pct.toStringAsFixed(0)}% gest.',
            style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }
}
