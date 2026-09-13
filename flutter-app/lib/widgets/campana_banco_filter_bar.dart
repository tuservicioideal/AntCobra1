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
  final bool compact;
  final bool dense;

  const CampanaBancoFilterBar({
    super.key,
    required this.available,
    required this.selected,
    required this.onSelected,
    this.compact = false,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    if (!campanaBancoFilterBarVisible(available)) {
      return const SizedBox.shrink();
    }

    if (compact) return _buildCompactMenu();
    if (dense) return _buildDenseChips();

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

  Widget _buildDenseChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _chip(
            value: null,
            label: 'Todas',
            icon: Icons.layers_outlined,
          ),
          for (final campana in available) ...[
            const SizedBox(width: 6),
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
    );
  }

  String _labelFor(String? value) {
    if (value == null) return 'Todas';
    if (value == kSinCampanaBancoKey) return kSinCampanaBancoLabel;
    return value;
  }

  Widget _buildCompactMenu() {
    const allValue = '__all__';
    return PopupMenuButton<String>(
      tooltip: 'Filtrar por N° campaña',
      onSelected: (value) =>
          onSelected(value == allValue ? null : value),
      itemBuilder: (context) => [
        PopupMenuItem(
          value: allValue,
          child: Text(
            'Todas',
            style: TextStyle(
              fontWeight: selected == null ? FontWeight.w700 : FontWeight.w400,
            ),
          ),
        ),
        for (final campana in available)
          PopupMenuItem(
            value: campana,
            child: Text(
              _labelFor(campana),
              style: TextStyle(
                fontWeight:
                    selected == campana ? FontWeight.w700 : FontWeight.w400,
              ),
            ),
          ),
      ],
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: selected != null
              ? AppTheme.primaryColor.withValues(alpha: 0.12)
              : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: selected != null
                ? AppTheme.primaryColor.withValues(alpha: 0.4)
                : Colors.grey.shade300,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.campaign_outlined,
              size: 15,
              color: selected != null
                  ? AppTheme.primaryColor
                  : Colors.grey.shade700,
            ),
            const SizedBox(width: 6),
            Text(
              _labelFor(selected),
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: selected != null
                    ? AppTheme.primaryColor
                    : Colors.grey.shade700,
              ),
            ),
            Icon(
              Icons.arrow_drop_down,
              size: 18,
              color: Colors.grey.shade600,
            ),
          ],
        ),
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
        padding: EdgeInsets.symmetric(
          horizontal: dense ? 8 : 12,
          vertical: dense ? 3 : 6,
        ),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.primaryColor : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(dense ? 12 : 20),
          border: Border.all(
            color: isActive ? AppTheme.primaryColor : Colors.grey.shade300,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (!dense) ...[
              Icon(
                icon,
                size: 14,
                color: isActive ? Colors.white : Colors.grey.shade600,
              ),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: dense ? 10 : 12,
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
