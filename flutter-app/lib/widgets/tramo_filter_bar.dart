import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../utils/tramo_filter.dart';

Color tramoAccentColor(int tramo) {
  final t = tramo <= 0 ? 1 : (tramo >= 3 ? 3 : tramo);
  switch (t) {
    case 2:
      return AppTheme.accentColor;
    case 3:
      return AppTheme.warning;
    default:
      return AppTheme.primaryColor;
  }
}

/// Badge compacto E1 / E2 / E3 para filas de cliente.
class TramoBadge extends StatelessWidget {
  final int tramo;
  final bool dense;

  const TramoBadge({
    super.key,
    required this.tramo,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    final label = tramoLabel(tramo);
    final color = tramoAccentColor(tramo);
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? 4 : 5,
        vertical: dense ? 1 : 2,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: dense ? 9 : 10,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}

/// Botones E1 / E2 / E3 para filtrar la cartera por etapa.
class TramoFilterBar extends StatelessWidget {
  final List<ClientModel> clients;
  final Set<int> selected;
  final ValueChanged<int> onTap;
  final bool compact;
  final bool expandedCards;
  final String keyPrefix;

  const TramoFilterBar({
    super.key,
    required this.clients,
    required this.selected,
    required this.onTap,
    this.compact = false,
    this.expandedCards = false,
    this.keyPrefix = 'tramo-filter',
  });

  @override
  Widget build(BuildContext context) {
    final counts = countByTramo(clients);
    if (expandedCards) {
      return Row(
        children: [
          for (var i = 0; i < tramoFilterOptions.length; i++) ...[
            if (i > 0) const SizedBox(width: 8),
            Expanded(
              child: _TramoFilterChip(
                tramo: tramoFilterOptions[i],
                count: counts[tramoFilterOptions[i]] ?? 0,
                selected: selected.contains(tramoFilterOptions[i]),
                onTap: () => onTap(tramoFilterOptions[i]),
                expanded: true,
                keyPrefix: keyPrefix,
              ),
            ),
          ],
        ],
      );
    }

    return Row(
      mainAxisSize: compact ? MainAxisSize.min : MainAxisSize.max,
      children: [
        for (var i = 0; i < tramoFilterOptions.length; i++) ...[
          if (i > 0) SizedBox(width: compact ? 6 : 8),
          _TramoFilterChip(
            tramo: tramoFilterOptions[i],
            count: counts[tramoFilterOptions[i]] ?? 0,
            selected: selected.contains(tramoFilterOptions[i]),
            onTap: () => onTap(tramoFilterOptions[i]),
            compact: compact,
            keyPrefix: keyPrefix,
          ),
        ],
      ],
    );
  }
}

class _TramoFilterChip extends StatelessWidget {
  final int tramo;
  final int count;
  final bool selected;
  final VoidCallback onTap;
  final bool compact;
  final bool expanded;
  final String keyPrefix;

  const _TramoFilterChip({
    required this.tramo,
    required this.count,
    required this.selected,
    required this.onTap,
    this.compact = false,
    this.expanded = false,
    this.keyPrefix = 'tramo-filter',
  });

  @override
  Widget build(BuildContext context) {
    final color = tramoAccentColor(tramo);
    final label = tramoLabel(tramo);
    final tooltip = selected
        ? 'Quitar filtro $label'
        : 'Filtrar por etapa $label';

    final child = expanded
        ? _expandedBody(label, color)
        : _compactBody(label, color);

    return Semantics(
      button: true,
      selected: selected,
      label: '$tooltip, $count cuentas',
      child: Tooltip(
        message: tooltip,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            key: ValueKey('$keyPrefix-$label'),
            onTap: onTap,
            borderRadius: BorderRadius.circular(8),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              constraints: BoxConstraints(minHeight: compact ? 36 : 44),
              padding: EdgeInsets.symmetric(
                horizontal: compact ? 8 : 6,
                vertical: compact ? 5 : 8,
              ),
              decoration: BoxDecoration(
                color: selected
                    ? color.withValues(alpha: 0.22)
                    : color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: selected ? color : color.withValues(alpha: 0.25),
                  width: selected ? 2 : 1,
                ),
              ),
              child: child,
            ),
          ),
        ),
      ),
    );
  }

  Widget _compactBody(String label, Color color) {
    return Text(
      '$label $count',
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        color: color,
      ),
    );
  }

  Widget _expandedBody(String label, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
        Text(
          '$count',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }
}
