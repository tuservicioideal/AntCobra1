import 'package:flutter/material.dart';

import '../../config/theme.dart';
import '../../models/campaign_stats.dart';
import '../../utils/stats_format.dart';

class GestorRankingPreview extends StatelessWidget {
  final List<GestorRankingEntry> entries;
  final VoidCallback? onViewAll;

  const GestorRankingPreview({
    super.key,
    required this.entries,
    this.onViewAll,
  });

  @override
  Widget build(BuildContext context) {
    final top = entries.take(3).toList();
    if (top.isEmpty) return const SizedBox.shrink();

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
                  'Top gestores',
                  style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                ),
                if (onViewAll != null)
                  TextButton(
                    onPressed: onViewAll,
                    child: const Text('Ver ranking'),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            ...top.asMap().entries.map((entry) {
              final i = entry.key;
              final g = entry.value;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 16,
                      backgroundColor:
                          AppTheme.primaryColor.withValues(alpha: 0.15),
                      child: Text(
                        '${i + 1}',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                          color: AppTheme.primaryColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            g.nombre,
                            style: const TextStyle(
                              fontWeight: FontWeight.w500,
                              fontSize: 13,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            '${g.gestiones} gest. · ${g.habidos} habidos',
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      formatMoneyCompact(g.recuperadoBanco),
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        color: Colors.teal.shade700,
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
