import 'package:flutter/material.dart';

import '../utils/responsive.dart';

/// Bottom sheet on compact screens; centered dialog on expanded (desktop web).
class AdaptiveSheet {
  AdaptiveSheet._();

  static Future<T?> show<T>({
    required BuildContext context,
    required WidgetBuilder builder,
    bool isScrollControlled = true,
    bool useRootNavigator = false,
    double? maxWidth,
    String? title,
  }) {
    if (context.isExpanded) {
      final width = maxWidth ?? context.dialogMaxWidth(560);
      return showDialog<T>(
        context: context,
        useRootNavigator: useRootNavigator,
        builder: (ctx) => Dialog(
          insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: width),
            child: title == null
                ? builder(ctx)
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(20, 16, 8, 0),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                title,
                                style: Theme.of(ctx).textTheme.titleMedium,
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.close),
                              onPressed: () => Navigator.pop(ctx),
                            ),
                          ],
                        ),
                      ),
                      Flexible(child: builder(ctx)),
                    ],
                  ),
          ),
        ),
      );
    }

    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: isScrollControlled,
      useRootNavigator: useRootNavigator,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: builder,
    );
  }
}
