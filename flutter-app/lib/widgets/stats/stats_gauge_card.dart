import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../config/theme.dart';

/// Semi-circular gauge using fl_chart pie sections.
class StatsGaugeCard extends StatelessWidget {
  final String label;
  final double value;
  final double max;
  final Color color;
  final String subtitle;

  const StatsGaugeCard({
    super.key,
    required this.label,
    required this.value,
    this.max = 100,
    required this.color,
    this.subtitle = '',
  });

  @override
  Widget build(BuildContext context) {
    final pct = max > 0 ? (value / max).clamp(0.0, 1.0) : 0.0;
    final display = max == 100
        ? '${(pct * 100).toStringAsFixed(0)}%'
        : value.toStringAsFixed(0);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
                letterSpacing: 0.3,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 110,
              width: 110,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  PieChart(
                    PieChartData(
                      startDegreeOffset: 180,
                      sectionsSpace: 0,
                      centerSpaceRadius: 36,
                      sections: [
                        PieChartSectionData(
                          value: pct * 100,
                          color: color,
                          radius: 14,
                          showTitle: false,
                        ),
                        PieChartSectionData(
                          value: (1 - pct) * 100,
                          color: Colors.grey.shade200,
                          radius: 14,
                          showTitle: false,
                        ),
                      ],
                    ),
                  ),
                  Text(
                    display,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryColor,
                    ),
                  ),
                ],
              ),
            ),
            if (subtitle.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
