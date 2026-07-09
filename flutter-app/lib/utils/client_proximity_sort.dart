import 'package:geolocator/geolocator.dart';

import '../models/client_model.dart';

/// Distancia en metros desde [originLat]/[originLng] al cliente, o null sin coords.
double? distanceMeters(
  ClientModel client,
  double originLat,
  double originLng,
) {
  if (!client.hasCoordinates) return null;
  return Geolocator.distanceBetween(
    originLat,
    originLng,
    client.latitude,
    client.longitude,
  );
}

/// Etiqueta legible: metros o kilómetros.
String formatDistanceMeters(double meters) {
  if (meters < 1000) {
    return '${meters.round()} m';
  }
  final km = meters / 1000;
  if (km < 10) {
    return '${km.toStringAsFixed(1)} km';
  }
  return '${km.round()} km';
}

/// Ordena por proximidad desde el origen. Con [pendingFirst], pendientes antes que visitados.
List<ClientModel> sortClientsByProximity(
  List<ClientModel> clients, {
  required double originLat,
  required double originLng,
  bool pendingFirst = true,
}) {
  if (clients.isEmpty) return [];

  final distances = <String, double?>{};
  for (final c in clients) {
    distances[c.id] = distanceMeters(c, originLat, originLng);
  }

  double sortDistance(ClientModel c) => distances[c.id] ?? double.infinity;

  final sorted = [...clients];
  sorted.sort((a, b) {
    if (pendingFirst) {
      final ap = a.isPendiente ? 0 : 1;
      final bp = b.isPendiente ? 0 : 1;
      if (ap != bp) return ap.compareTo(bp);
    }
    final da = sortDistance(a);
    final db = sortDistance(b);
    if (da != db) return da.compareTo(db);
    return a.displayName.compareTo(b.displayName);
  });
  return sorted;
}

/// Etiqueta de distancia para un cliente, o null si no aplica.
String? distanceLabelForClient(
  ClientModel client,
  double? originLat,
  double? originLng,
) {
  if (originLat == null || originLng == null) return null;
  final meters = distanceMeters(client, originLat, originLng);
  if (meters == null) return null;
  return formatDistanceMeters(meters);
}
