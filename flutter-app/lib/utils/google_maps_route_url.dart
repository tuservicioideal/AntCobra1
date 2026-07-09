import 'package:latlong2/latlong.dart';

/// Resultado al construir URL de Google Maps (puede truncar paradas).
class GoogleMapsRouteUrlResult {
  const GoogleMapsRouteUrlResult({
    required this.uri,
    required this.exportedStopCount,
    required this.totalStopCount,
    required this.wasTruncated,
  });

  final Uri uri;
  final int exportedStopCount;
  final int totalStopCount;
  final bool wasTruncated;
}

/// Límite de paradas intermedias en Maps URLs (app Android / escritorio).
const int kGoogleMapsMaxWaypoints = 9;

/// Longitud máxima recomendada de URL.
const int kGoogleMapsMaxUrlLength = 2048;

String _coord(LatLng p) => '${p.latitude},${p.longitude}';

/// Recorta [stops] para caber en origin + waypoints + destination.
/// Retorna (stops exportados, total original, truncado).
({List<LatLng> exported, int total, bool truncated}) trimStopsForGoogleMaps(
  List<LatLng> stops, {
  int maxWaypoints = kGoogleMapsMaxWaypoints,
}) {
  if (stops.isEmpty) {
    return (exported: const [], total: 0, truncated: false);
  }
  // origin + maxWaypoints intermedios + destination => maxWaypoints + 2 puntos
  final maxPoints = maxWaypoints + 2;
  if (stops.length <= maxPoints) {
    return (exported: stops, total: stops.length, truncated: false);
  }
  return (
    exported: stops.sublist(0, maxPoints),
    total: stops.length,
    truncated: true,
  );
}

/// Construye URL de direcciones con origen, paradas intermedias y destino.
///
/// [clientStops] — clientes ordenados (sin GPS del gestor).
/// [origin] — ubicación actual; si es null, el primer stop es origen.
GoogleMapsRouteUrlResult buildGoogleMapsDrivingUrl({
  required List<LatLng> clientStops,
  LatLng? origin,
}) {
  final allStops = <LatLng>[
    if (origin != null) origin,
    ...clientStops,
  ];

  if (allStops.isEmpty) {
    throw ArgumentError('Se requiere al menos un punto para la ruta.');
  }

  final trimmed = trimStopsForGoogleMaps(allStops);
  final points = trimmed.exported;

  late final String originParam;
  late final String destinationParam;
  String? waypointsParam;

  if (points.length == 1) {
    originParam = _coord(points.first);
    destinationParam = originParam;
  } else {
    originParam = _coord(points.first);
    destinationParam = _coord(points.last);
    if (points.length > 2) {
      final middle = points.sublist(1, points.length - 1);
      waypointsParam = middle.map(_coord).join('|');
    }
  }

  final query = <String, String>{
    'api': '1',
    'origin': originParam,
    'destination': destinationParam,
    'travelmode': 'driving',
    if (waypointsParam != null && waypointsParam.isNotEmpty) 'waypoints': waypointsParam,
  };

  final uri = Uri.https('www.google.com', '/maps/dir/', query);

  return GoogleMapsRouteUrlResult(
    uri: uri,
    exportedStopCount: points.length,
    totalStopCount: trimmed.total,
    wasTruncated: trimmed.truncated,
  );
}
