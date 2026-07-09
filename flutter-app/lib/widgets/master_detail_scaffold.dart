import 'package:flutter/material.dart';

import '../utils/responsive.dart';

/// Master-detail layout for wide screens; stacks vertically on compact.
class MasterDetailScaffold extends StatelessWidget {
  final Widget header;
  final Widget master;
  final Widget? detail;
  final Widget emptyDetail;
  final double masterFlex;
  final double detailFlex;

  const MasterDetailScaffold({
    super.key,
    required this.header,
    required this.master,
    this.detail,
    required this.emptyDetail,
    this.masterFlex = 2,
    this.detailFlex = 3,
  });

  @override
  Widget build(BuildContext context) {
    final detailPane = detail ?? emptyDetail;

    if (!context.isExpanded) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          header,
          Expanded(child: master),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        header,
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                flex: masterFlex.round(),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    minWidth: ResponsiveBreakpoints.masterPaneMin,
                  ),
                  child: master,
                ),
              ),
              const VerticalDivider(width: 1),
              Expanded(
                flex: detailFlex.round(),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    minWidth: ResponsiveBreakpoints.detailPaneMin,
                  ),
                  child: detailPane,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Placeholder shown in the detail pane when nothing is selected.
class MasterDetailEmptyPlaceholder extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;

  const MasterDetailEmptyPlaceholder({
    super.key,
    this.icon = Icons.touch_app_outlined,
    this.title = 'Selecciona un cliente',
    this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(
              title,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
              textAlign: TextAlign.center,
            ),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(
                subtitle!,
                style: TextStyle(fontSize: 13, color: Colors.grey.shade500),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
