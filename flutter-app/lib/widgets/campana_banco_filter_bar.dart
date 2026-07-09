import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../config/theme.dart';
import '../utils/campana_banco_utils.dart';

/// Chips horizontales para filtrar clientes por **Nº campaña banco**.
///
/// Se oculta automáticamente si solo hay una campaña (sin ruido en UI).
class CampanaBancoFilterBar extends StatelessWidget {
  final List<String> available;
  final String? selected;
  final ValueChanged<String?> onSelected;

  const CampanaBancoFilterBar({
    super.key,
    required this.available,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    if (!campanaBancoFilterBarVisible(available)) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Nº campaña',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade600,
            ),
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _chip(
                  value: null,
                  label: 'Todas',
                  icon: Icons.layers_outlined,
                ),
                for (final campana in available) ...[
                  const SizedBox(width: 8),
                  _chip(
                    value: campana,
                    label: campana == kSinCampanaBancoKey
                        ? kSinCampanaBancoLabel
                        : campana,
                    icon: Icons.campaign_outlined,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip({
    required String? value,
    required String label,
    required IconData icon,
  }) {
    final isActive = selected == value;
    return GestureDetector(
      onTap: () => onSelected(value),
      child: AnimatedContainer(
        duration: 200.ms,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.primaryColor : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isActive ? AppTheme.primaryColor : Colors.grey.shade300,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 14,
              color: isActive ? Colors.white : Colors.grey.shade600,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: isActive ? Colors.white : Colors.grey.shade600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
