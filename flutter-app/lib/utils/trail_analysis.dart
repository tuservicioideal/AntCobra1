import '../models/client_model.dart';
import '../models/tracking_models.dart';
import 'trail_filter.dart';

/// Clasificación de un cliente respecto al recorrido GPS del gestor.
enum ClientTrailStatus {
  /// Hay punto `tipo=visita` vinculado al cliente ese día.
  managed,

  /// El trail pasó a ≤ [TrailAnalysis.proximityRadiusMeters] sin visita registrada.
  nearbyWithoutVisit,

  /// No se acercó al domicilio del cliente.
  notApproached,
}

/// Resultado de proximidad trail ↔ cliente.
class ClientProximityResult {
  final ClientModel client;
  final ClientTrailStatus status;
  final double minDistanceMeters;
  final TrailPoint? closestPoint;
  final TrailPoint? visitPoint;

  const ClientProximityResult({
    required this.client,
    required this.status,
    required this.minDistanceMeters,
    this.closestPoint,
    this.visitPoint,
  });

  bool get wasManaged => status == ClientTrailStatus.managed;
  bool get passedNearby => status == ClientTrailStatus.nearbyWithoutVisit;
}

/// Análisis de proximidad entre trail filtrado y clientes de la sección.
class TrailAnalysis {
  TrailAnalysis({this.proximityRadiusMeters = 80});

  final double proximityRadiusMeters;

  /// Analiza clientes activos con coordenadas contra el trail del día.
  List<ClientProximityResult> analyze({
    required FilteredTrail trail,
    required List<ClientModel> clients,
  }) {
    final flat = trail.kept;
    final visits = trail.visitPoints;
    final results = <ClientProximityResult>[];

    for (final client in clients) {
      if (!client.hasCoordinates) continue;

      TrailPoint? visitMatch;
      for (final v in visits) {
        if (_visitMatchesClient(v, client)) {
          visitMatch = v;
          break;
        }
      }

      double minDist = double.infinity;
      TrailPoint? closest;
      for (final p in flat) {
        final d = TrackingGeo.haversineKm(
              client.latitude,
              client.longitude,
              p.lat,
              p.lng,
            ) *
            1000;
        if (d < minDist) {
          minDist = d;
          closest = p;
        }
      }
      if (minDist == double.infinity) minDist = -1;

      final ClientTrailStatus status;
      if (visitMatch != null) {
        status = ClientTrailStatus.managed;
      } else if (minDist >= 0 && minDist <= proximityRadiusMeters) {
        status = ClientTrailStatus.nearbyWithoutVisit;
      } else {
        status = ClientTrailStatus.notApproached;
      }

      results.add(ClientProximityResult(
        client: client,
        status: status,
        minDistanceMeters: minDist,
        closestPoint: closest,
        visitPoint: visitMatch,
      ));
    }

    results.sort((a, b) {
      final oa = _statusOrder(a.status);
      final ob = _statusOrder(b.status);
      if (oa != ob) return oa.compareTo(ob);
      final da = a.minDistanceMeters < 0 ? double.infinity : a.minDistanceMeters;
      final db = b.minDistanceMeters < 0 ? double.infinity : b.minDistanceMeters;
      return da.compareTo(db);
    });
    return results;
  }

  /// Distancia en metros entre el GPS de la visita y el domicilio del cliente.
  static double? visitToHomeDistanceMeters(
    TrailPoint visit,
    ClientModel client,
  ) {
    if (!client.hasCoordinates) return null;
    return TrackingGeo.haversineKm(
          visit.lat,
          visit.lng,
          client.latitude,
          client.longitude,
        ) *
        1000;
  }

  static bool _visitMatchesClient(TrailPoint visit, ClientModel client) {
    if (visit.clienteId.isNotEmpty &&
        (visit.clienteId == client.id ||
            visit.clienteId == client.codigoCliente)) {
      return true;
    }
    if (visit.cliente.isNotEmpty &&
        client.displayName.isNotEmpty &&
        visit.cliente.toLowerCase() == client.displayName.toLowerCase()) {
      return true;
    }
    return false;
  }

  static int _statusOrder(ClientTrailStatus s) {
    switch (s) {
      case ClientTrailStatus.managed:
        return 0;
      case ClientTrailStatus.nearbyWithoutVisit:
        return 1;
      case ClientTrailStatus.notApproached:
        return 2;
    }
  }
}
