import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Breakpoints aligned with [HomeShell] navigation rail threshold.
abstract final class ResponsiveBreakpoints {
  static const double compact = 600;
  static const double expanded = 900;
  static const double contentMax = 1280;
  static const double masterPaneMin = 500;
  static const double detailPaneMin = 340;

  /// Split a wide layout into list (master) and ficha (detail) panes.
  static ({double master, double detail}) masterDetailWidths({
    required double total,
    double masterFlex = 5,
    double detailFlex = 3,
    double divider = 1,
  }) {
    final usable = math.max(0.0, total - divider);
    final flexSum = math.max(1.0, masterFlex + detailFlex);
    var detailW = usable * (detailFlex / flexSum);
    var masterW = usable - detailW;

    if (masterW < masterPaneMin) {
      masterW = math.min(masterPaneMin, usable * 0.72);
      detailW = usable - masterW;
    }
    if (detailW < detailPaneMin) {
      detailW = math.min(detailPaneMin, usable * 0.38);
      masterW = usable - detailW;
    }
    return (master: masterW, detail: detailW);
  }
}

enum ResponsiveSize {
  compact,
  medium,
  expanded,
}

extension ResponsiveContext on BuildContext {
  double get screenWidth => MediaQuery.sizeOf(this).width;

  ResponsiveSize get responsiveSize {
    final w = screenWidth;
    if (w >= ResponsiveBreakpoints.expanded) return ResponsiveSize.expanded;
    if (w >= ResponsiveBreakpoints.compact) return ResponsiveSize.medium;
    return ResponsiveSize.compact;
  }

  bool get isCompact => responsiveSize == ResponsiveSize.compact;
  bool get isMedium => responsiveSize == ResponsiveSize.medium;
  bool get isExpanded => responsiveSize == ResponsiveSize.expanded;

  /// Dialog/sheet width capped for the current viewport.
  double dialogMaxWidth([double preferred = 520]) {
    return math.min(preferred, screenWidth * 0.9);
  }
}
