import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../config/theme.dart';

class StatsPieEntry {
  final String label;
  final int value;
  final Color color;

  const StatsPieEntry(this.label, this.value, this.color);
}

class StatsPieChart extends StatelessWidget {
  final List<StatsPieEntry> entries;
  final int total;
  final double size;
  final bool showLegend;

  const StatsPieChart({
    super.key,
    required this.entries,
    required this.total,
    this.size = 200,
    this.showLegend = true,
  });

  @override
  Widget build(BuildContext context) {
    final visible = entries.where((e) => e.value > 0).toList();
    if (visible.isEmpty) return const SizedBox.shrink();

    return Column(
      children: [
        SizedBox(
          height: size,
          width: size,
          child: CustomPaint(
            painter: _StatsPieChartPainter(visible, total),
          ),
        ),
        if (showLegend) ...[
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 6,
            children: visible
                .map(
                  (e) => Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: e.color,
                          borderRadius: BorderRadius.circular(3),
                        ),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '${e.label}: ${e.value}',
                        style: const TextStyle(fontSize: 11),
                      ),
                    ],
                  ),
                )
                .toList(),
          ),
        ],
      ],
    );
  }
}

class _StatsPieChartPainter extends CustomPainter {
  final List<StatsPieEntry> entries;
  final int total;

  _StatsPieChartPainter(this.entries, this.total);

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 8;
    var startAngle = -math.pi / 2;
    final sum = entries.fold<int>(0, (s, e) => s + e.value);
    final denom = sum > 0 ? sum : total;

    for (final entry in entries) {
      final sweep = denom > 0 ? (entry.value / denom) * 2 * math.pi : 0.0;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        startAngle,
        sweep,
        true,
        Paint()..color = entry.color,
      );
      startAngle += sweep;
    }

    canvas.drawCircle(center, radius * 0.55, Paint()..color = Colors.white);

    final textPainter = TextPainter(
      text: TextSpan(
        text: '$total',
        style: const TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.bold,
          color: AppTheme.primaryColor,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(
      canvas,
      Offset(
        center.dx - textPainter.width / 2,
        center.dy - textPainter.height / 2,
      ),
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
