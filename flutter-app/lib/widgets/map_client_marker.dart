import 'package:flutter/material.dart';
import '../config/theme.dart';
import '../models/client_model.dart';

/// Pin de cliente en el mapa (área táctil ≥ 48 px, sin etiqueta de nombre).
class MapClientMarker extends StatelessWidget {
  const MapClientMarker({
    super.key,
    required this.client,
    required this.onRoute,
    required this.focused,
    this.onTap,
  });

  final ClientModel client;
  final bool onRoute;
  final bool focused;
  final VoidCallback? onTap;

  static const double hitSize = 48;

  @override
  Widget build(BuildContext context) {
    final iconSize = onRoute ? 34.0 : 30.0;
    final iconColor =
        onRoute ? Colors.green.shade700 : AppTheme.primaryColor;

    final visual = SizedBox(
      width: hitSize,
      height: hitSize,
      child: Center(
        child: Stack(
          alignment: Alignment.center,
          clipBehavior: Clip.none,
          children: [
            if (focused)
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.amber.shade600, width: 2.5),
                ),
              ),
            Icon(Icons.location_on, color: iconColor, size: iconSize),
            if (onRoute)
              Positioned(
                right: 6,
                top: 4,
                child: Container(
                  padding: const EdgeInsets.all(1.5),
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.check,
                    size: 11,
                    color: Colors.green.shade700,
                  ),
                ),
              ),
          ],
        ),
      ),
    );

    if (onTap == null) return visual;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: visual,
    );
  }
}
