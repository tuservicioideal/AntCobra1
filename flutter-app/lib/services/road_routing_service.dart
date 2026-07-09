import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../config/routing_config.dart';

class RoadRouteResult {
  const RoadRouteResult({
    required this.points,
    required this.distanceMeters,
    required this.durationSeconds,
  });

  final List<LatLng> points;
  final double distanceMeters;
  final double durationSeconds;

  double get distanceKm => distanceMeters / 1000;
  double get durationMinutes => durationSeconds / 60;
}

class RoadRoutingException implements Exception {
  RoadRoutingException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Obtiene geometría de ruta por carretera vía OSRM (servidor público).
class RoadRoutingService {
  RoadRoutingService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<RoadRouteResult> fetchRoute(List<LatLng> waypoints) async {
    if (waypoints.length < 2) {
      throw RoadRoutingException('Se necesitan al menos 2 puntos.');
    }

    final coords = waypoints.length > RoutingConfig.maxOsrmCoordinates
        ? waypoints.sublist(0, RoutingConfig.maxOsrmCoordinates)
        : waypoints;

    if (waypoints.length > RoutingConfig.maxOsrmCoordinates) {
      return _fetchRouteSegmented(waypoints);
    }

    return _fetchSingleRoute(coords);
  }

  Future<RoadRouteResult> _fetchRouteSegmented(List<LatLng> waypoints) async {
    final allPoints = <LatLng>[];
    var totalDistance = 0.0;
    var totalDuration = 0.0;
    final step = RoutingConfig.maxOsrmCoordinates - 1;

    for (var i = 0; i < waypoints.length - 1; i += step) {
      final end = (i + RoutingConfig.maxOsrmCoordinates).clamp(0, waypoints.length);
      if (end <= i + 1) break;
      final chunk = waypoints.sublist(i, end);

      final segment = await _fetchSingleRoute(chunk);
      if (allPoints.isNotEmpty && segment.points.isNotEmpty) {
        allPoints.addAll(segment.points.skip(1));
      } else {
        allPoints.addAll(segment.points);
      }
      totalDistance += segment.distanceMeters;
      totalDuration += segment.durationSeconds;

      if (end >= waypoints.length) break;
    }

    if (allPoints.isEmpty) {
      throw RoadRoutingException('No se pudo calcular la ruta por segmentos.');
    }

    return RoadRouteResult(
      points: allPoints,
      distanceMeters: totalDistance,
      durationSeconds: totalDuration,
    );
  }

  Future<RoadRouteResult> _fetchSingleRoute(List<LatLng> waypoints) async {
    final coordPath = waypoints
        .map((p) => '${p.longitude},${p.latitude}')
        .join(';');

    final uri = Uri.parse('${RoutingConfig.baseUrl}/route/v1/${RoutingConfig.profile}/$coordPath')
        .replace(
      queryParameters: {
        'overview': 'full',
        'geometries': 'geojson',
        'steps': 'false',
      },
    );

    final response = await _client
        .get(uri)
        .timeout(RoutingConfig.requestTimeout);

    if (response.statusCode != 200) {
      throw RoadRoutingException('OSRM respondió ${response.statusCode}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final code = data['code']?.toString();
    if (code != 'Ok') {
      throw RoadRoutingException(data['message']?.toString() ?? 'Ruta no disponible');
    }

    final routes = data['routes'] as List?;
    if (routes == null || routes.isEmpty) {
      throw RoadRoutingException('Sin rutas en la respuesta');
    }

    final route = routes.first as Map<String, dynamic>;
    final geometry = route['geometry'] as Map<String, dynamic>?;
    final coordinates = geometry?['coordinates'] as List?;

    if (coordinates == null || coordinates.isEmpty) {
      throw RoadRoutingException('Geometría vacía');
    }

    final points = <LatLng>[];
    for (final coord in coordinates) {
      if (coord is! List || coord.length < 2) continue;
      final lng = (coord[0] as num).toDouble();
      final lat = (coord[1] as num).toDouble();
      points.add(LatLng(lat, lng));
    }

    return RoadRouteResult(
      points: points,
      distanceMeters: (route['distance'] as num?)?.toDouble() ?? 0,
      durationSeconds: (route['duration'] as num?)?.toDouble() ?? 0,
    );
  }

  void dispose() {
    _client.close();
  }
}
