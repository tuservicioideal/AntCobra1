import 'package:flutter/material.dart';
import '../../config/theme.dart';

/// Collapsible section wrapper for client detail accordions.
class DetailSectionTile extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;
  final bool initiallyExpanded;
  final EdgeInsetsGeometry? childPadding;

  const DetailSectionTile({
    super.key,
    required this.title,
    required this.icon,
    required this.child,
    this.initiallyExpanded = false,
    this.childPadding = const EdgeInsets.fromLTRB(12, 0, 12, 12),
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: initiallyExpanded,
          tilePadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          childrenPadding: childPadding ?? EdgeInsets.zero,
          leading: Icon(icon, size: 20, color: AppTheme.primary),
          title: Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 14,
              color: AppTheme.textPrimary,
            ),
          ),
          iconColor: AppTheme.textSecondary,
          collapsedIconColor: AppTheme.textSecondary,
          children: [child],
        ),
      ),
    );
  }
}
