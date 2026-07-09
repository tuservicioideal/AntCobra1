import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Breakpoints aligned with [HomeShell] navigation rail threshold.
abstract final class ResponsiveBreakpoints {
  static const double compact = 600;
  static const double expanded = 900;
  static const double contentMax = 1280;
  static const double masterPaneMin = 380;
  static const double detailPaneMin = 480;
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
