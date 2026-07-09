import 'package:flutter/material.dart';

import '../../config/theme.dart';
import '../../models/campaign_stats.dart';
import '../../utils/stats_format.dart';

class StatsRankingList extends StatelessWidget {
  final List<GestorRankingEntry> entries;

  const StatsRankingList({super.key, required this.entries});

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Text(
              'Aún no hay gestiones atribuidas a gestores.',
              style: TextStyle(color: Colors.grey.shade600),
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }

    final maxRec = entries.first.recuperadoBanco;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Top gestores por recuperación (banco)',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
            ),
            const SizedBox(height: 12),
            ...entries.asMap().entries.map((e) {
              final i = e.key;
              final g = e.value;
              final bar = maxRec > 0 ? g.recuperadoBanco / maxRec : 0.0;
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 14,
                          backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.15),
                          child: Text(
                            '${i + 1}',
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.primaryColor,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            g.nombre,
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Text(
                          formatMoneyCompact(g.recuperadoBanco),
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: bar,
                        minHeight: 8,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          Color.lerp(Colors.orange, Colors.green, bar) ??
                              AppTheme.primaryColor,
                        ),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${g.gestiones} gest. · ${g.habidos} habidos · '
                      '${g.promesasCount} promesas',
                      style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
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
