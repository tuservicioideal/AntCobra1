import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

import '../utils/map_error_logger.dart';

/// Configuración centralizada de proveedores de tiles para flutter_map.
class MapTileSource {
  final String name;
  final String urlTemplate;
  final String? fallbackUrlTemplate;
  final List<String> subdomains;
  final String attribution;
  final int maxNativeZoom;

  const MapTileSource({
    required this.name,
    required this.urlTemplate,
    this.fallbackUrlTemplate,
    this.subdomains = const [],
    required this.attribution,
    this.maxNativeZoom = 19,
  });
}

/// OSM directo sin subdominios — seguro como fallback (no usa `{s}`).
const _osmRasterFallback = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

class MapTilesConfig {
  static const String userAgentPackageName = 'com.fym.recaudolegal';

  static final ValueNotifier<int> tileErrorCount = ValueNotifier<int>(0);
  static bool _persistScheduled = false;

  /// Carto primero (estable en APK); OSM y Esri como alternativas.
  static const List<MapTileSource> sources = [
    MapTileSource(
      name: 'Carto Voyager',
      urlTemplate:
          'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
      subdomains: ['a', 'b', 'c', 'd'],
      fallbackUrlTemplate: _osmRasterFallback,
      attribution: '© CARTO © OpenStreetMap',
      maxNativeZoom: 20,
    ),
    MapTileSource(
      name: 'OpenStreetMap',
      urlTemplate: _osmRasterFallback,
      fallbackUrlTemplate:
          'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
      subdomains: ['a', 'b', 'c', 'd'],
      attribution: '© OpenStreetMap contributors',
    ),
    MapTileSource(
      name: 'Esri Calles',
      urlTemplate:
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      fallbackUrlTemplate: _osmRasterFallback,
      attribution: '© Esri',
      maxNativeZoom: 19,
    ),
  ];

  static MapTileSource sourceAt(int index) =>
      sources[index.clamp(0, sources.length - 1)];

  static void resetTileErrors() {
    tileErrorCount.value = 0;
    _persistScheduled = false;
  }

  static void _recordTileError(Object error, StackTrace? stackTrace) {
    tileErrorCount.value = tileErrorCount.value + 1;
    MapErrorLogger.log('tile_load', error, stackTrace);
    if (!_persistScheduled) {
      _persistScheduled = true;
      MapErrorLogger.persistLastError('tile_load', error);
    }
  }

  static TileLayer buildTileLayer({
    required int sourceIndex,
    Key? key,
  }) {
    final src = sourceAt(sourceIndex);
    return TileLayer(
      key: key ?? ValueKey('tiles-$sourceIndex-${src.urlTemplate}'),
      urlTemplate: src.urlTemplate,
      fallbackUrl: src.fallbackUrlTemplate,
      subdomains: src.subdomains,
      userAgentPackageName: userAgentPackageName,
      minZoom: 0,
      maxZoom: 19,
      maxNativeZoom: src.maxNativeZoom,
      keepBuffer: 6,
      panBuffer: 2,
      evictErrorTileStrategy: EvictErrorTileStrategy.notVisibleRespectMargin,
      errorTileCallback: (tile, error, stackTrace) {
        _recordTileError(error, stackTrace);
      },
    );
  }

  static Widget buildAttribution(int sourceIndex) {
    final src = sourceAt(sourceIndex);
    return SimpleAttributionWidget(
      source: Text(src.attribution, style: const TextStyle(fontSize: 10)),
    );
  }

  static List<PopupMenuEntry<int>> buildSourceMenuItems() {
    return List.generate(
      sources.length,
      (i) => PopupMenuItem(value: i, child: Text(sources[i].name)),
    );
  }
}

/// Refresca el mapa tras volverse visible (p. ej. pestaña en IndexedStack).
void refreshMapTiles(MapController controller) {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    try {
      final cam = controller.camera;
      controller.move(cam.center, cam.zoom);
    } catch (_) {
      // El controlador aún no está listo.
    }
  });
}
