import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

import '../config/map_tiles.dart';

/// Notifica a pantallas con mapa cuando su pestaña pasa a estar activa.
class MapVisibilityScope extends InheritedWidget {
  const MapVisibilityScope({
    super.key,
    required this.isActive,
    required super.child,
  });

  final bool isActive;

  static bool isTabActive(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<MapVisibilityScope>();
    // Sin scope (pantalla abierta con Navigator): el mapa debe mostrarse siempre.
    return scope?.isActive ?? true;
  }

  @override
  bool updateShouldNotify(MapVisibilityScope oldWidget) =>
      oldWidget.isActive != isActive;
}

/// Envuelve una pestaña del shell y marca si está visible en el IndexedStack.
class MapTabWrapper extends StatelessWidget {
  const MapTabWrapper({
    super.key,
    required this.isActive,
    required this.child,
  });

  final bool isActive;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return MapVisibilityScope(isActive: isActive, child: child);
  }
}

/// Refresca tiles cuando la pestaña del mapa se activa en el shell.
mixin MapTabVisibilityMixin<T extends StatefulWidget> on State<T> {
  MapController get mapControllerForRefresh;

  bool _mapTabWasActive = false;
  bool _mapTabEverActivated = false;

  /// Incrementar solo al cambiar proveedor de tiles (no en cada activación de tab).
  int mapMountGeneration = 0;

  void bumpTileLayerGeneration() {
    mapMountGeneration += 1;
  }

  bool get isMapTabActive => MapVisibilityScope.isTabActive(context);

  /// Primera vez que la pestaña Mapa queda visible (IndexedStack).
  void onMapTabFirstVisible() {}

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _handleMapTabVisibility();
  }

  @override
  void didUpdateWidget(covariant T oldWidget) {
    super.didUpdateWidget(oldWidget);
    _handleMapTabVisibility();
  }

  void _handleMapTabVisibility() {
    final isActive = isMapTabActive;
    if (isActive && !_mapTabWasActive) {
      _mapTabWasActive = true;
      final firstActivation = !_mapTabEverActivated;
      if (firstActivation) {
        _mapTabEverActivated = true;
        onMapTabFirstVisible();
      }
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        setState(() {});
        refreshMapTiles(mapControllerForRefresh);
      });
      return;
    }
    if (!isActive) {
      _mapTabWasActive = false;
      return;
    }
    refreshMapTiles(mapControllerForRefresh);
  }
}
