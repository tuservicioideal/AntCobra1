import 'package:latlong2/latlong.dart';

const _distance = Distance();

/// Ordena clientes por cercanía sucesiva (haversine) desde [origin] o el primero.
List<Map<String, dynamic>> orderClientsByNearest(
  List<Map<String, dynamic>> clients,
  LatLng? origin,
) {
  if (clients.isEmpty) return [];

  final pending = [...clients];
  final ordered = <Map<String, dynamic>>[];
  LatLng current = origin ??
      LatLng(
        (pending.first['lat'] as num).toDouble(),
        (pending.first['lng'] as num).toDouble(),
      );

  while (pending.isNotEmpty) {
    var bestIndex = 0;
    var bestMeters = double.infinity;
    for (var i = 0; i < pending.length; i++) {
      final lat = (pending[i]['lat'] as num).toDouble();
      final lng = (pending[i]['lng'] as num).toDouble();
      final meters = _distance.as(LengthUnit.Meter, current, LatLng(lat, lng));
      if (meters < bestMeters) {
        bestMeters = meters;
        bestIndex = i;
      }
    }
    final next = pending.removeAt(bestIndex);
    ordered.add(next);
    current = LatLng(
      (next['lat'] as num).toDouble(),
      (next['lng'] as num).toDouble(),
    );
  }
  return ordered;
}

List<LatLng> clientMapsToLatLng(List<Map<String, dynamic>> clients) {
  return clients
      .map(
        (c) => LatLng(
          (c['lat'] as num).toDouble(),
          (c['lng'] as num).toDouble(),
        ),
      )
      .toList();
}

List<Map<String, dynamic>> parseRouteClients(List? raw) {
  return (raw ?? const [])
      .map(
        (e) => e is Map
            ? e.map((k, v) => MapEntry(k.toString(), v))
            : <String, dynamic>{},
      )
      .where((c) => (c['lat'] as num?) != null && (c['lng'] as num?) != null)
      .toList();
}
