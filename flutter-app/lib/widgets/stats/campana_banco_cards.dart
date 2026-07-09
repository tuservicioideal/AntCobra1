import 'package:flutter/material.dart';

import '../../config/theme.dart';
import '../../utils/campana_banco_utils.dart';
import '../../utils/stats_format.dart';

class CampanaBancoCards extends StatelessWidget {
  final List<CampanaBancoBreakdownEntry> entries;
  final String? selectedKey;
  final ValueChanged<String?>? onSelected;

  const CampanaBancoCards({
    super.key,
    required this.entries,
    this.selectedKey,
    this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            'Campañas banco activas',
            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
          ),
        ),
        SizedBox(
          height: 118,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: entries.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (context, index) {
              final e = entries[index];
              final isSelected = selectedKey == e.key;
              return InkWell(
                onTap: onSelected != null
                    ? () => onSelected!(isSelected ? null : e.key)
                    : null,
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  width: 160,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppTheme.primaryColor.withValues(alpha: 0.12)
                        : Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isSelected
                          ? AppTheme.primaryColor
                          : Colors.grey.shade300,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 4,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        e.label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${e.cuentas} cuentas · E${e.tramoPromedio}',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade600,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '${e.pctRecuperacion.toStringAsFixed(1)}% recup.',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.teal.shade700,
                          fontSize: 13,
                        ),
                      ),
                      Text(
                        formatMoneyCompact(e.recuperado),
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
