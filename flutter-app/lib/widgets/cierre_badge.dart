import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../utils/cierre_filter.dart';

/// Badge compacto de fecha de cierre / días restantes.
class CierreBadge extends StatelessWidget {
  final ClientModel client;
  final DateTime now;
  final int duracionDias;
  final bool dense;

  const CierreBadge({
    super.key,
    required this.client,
    required this.now,
    this.duracionDias = 59,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    final cierre = resolveFechaCierre(client, duracionDias: duracionDias);
    final label = formatCierreBadge(cierre: cierre, now: now);
    if (label.isEmpty) return const SizedBox.shrink();

    final level = cierreUrgencyLevel(cierre: cierre, now: now);
    final Color fg;
    final Color bg;
    switch (level) {
      case 3:
        fg = AppTheme.danger;
        bg = AppTheme.dangerLight;
      case 2:
        fg = AppTheme.warning;
        bg = AppTheme.warningLight;
      case 1:
        fg = const Color(0xFFB45309);
        bg = AppTheme.warningLight;
      default:
        fg = AppTheme.textSecondary;
        bg = AppTheme.divider;
    }

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? 5 : 6,
        vertical: dense ? 1 : 2,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontSize: dense ? 9 : 10,
          fontWeight: FontWeight.w600,
          color: fg,
        ),
      ),
    );
  }
}
