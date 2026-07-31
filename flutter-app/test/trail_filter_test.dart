import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/models/tracking_models.dart';
import 'package:app_recaudo_legal/utils/trail_analysis.dart';
import 'package:app_recaudo_legal/utils/trail_filter.dart';

TrailPoint _p({
  required double lat,
  required double lng,
  double accuracy = 10,
  String tipo = 'auto',
  String cliente = '',
  String clienteId = '',
  String estado = '',
  DateTime? time,
}) {
  final t = time ?? DateTime(2026, 7, 30, 10, 0);
  return TrailPoint(
    lat: lat,
    lng: lng,
    fecha: t.toIso8601String(),
    fechaDia: '2026-07-30',
    tipo: tipo,
    cliente: cliente,
    clienteId: clienteId,
    estado: estado,
    accuracy: accuracy,
    timestamp: Timestamp.fromDate(t),
  );
}

void main() {
  group('TrailFilter', () {
    final filter = TrailFilter(
      maxAccuracyMeters: 50,
      maxJumpSpeedKmh: 130,
      maxGapMinutes: 15,
      stayRadiusMeters: 25,
      stayMinMinutes: 3,
    );

    test('descarta puntos auto con mala accuracy', () {
      final raw = [
        _p(lat: -12.0, lng: -77.0, accuracy: 10),
        _p(lat: -12.0001, lng: -77.0, accuracy: 120),
        _p(lat: -12.0002, lng: -77.0, accuracy: 15, time: DateTime(2026, 7, 30, 10, 1)),
      ];
      final result = filter.filter(raw);
      expect(result.kept.length, 2);
      expect(result.rejected.length, 1);
      expect(result.rejected.first.reason, TrailRejectReason.badAccuracy);
    });

    test('nunca descarta puntos de visita aunque accuracy sea mala', () {
      final raw = [
        _p(lat: -12.0, lng: -77.0, accuracy: 10),
        _p(
          lat: -12.0001,
          lng: -77.0,
          accuracy: 200,
          tipo: 'visita',
          cliente: 'Juan',
          clienteId: 'c1',
          time: DateTime(2026, 7, 30, 10, 1),
        ),
      ];
      final result = filter.filter(raw);
      expect(result.kept.length, 2);
      expect(result.rejected, isEmpty);
      expect(result.visitPoints.length, 1);
    });

    test('corta segmento ante salto imposible', () {
      // ~11 km en 10 segundos ≈ 4000 km/h
      final raw = [
        _p(lat: -12.0, lng: -77.0, time: DateTime(2026, 7, 30, 10, 0, 0)),
        _p(lat: -12.1, lng: -77.0, time: DateTime(2026, 7, 30, 10, 0, 10)),
      ];
      final result = filter.filter(raw);
      expect(result.segments.length, 2);
      expect(result.km, lessThan(0.01)); // cada segmento de 1 punto = 0 km
    });

    test('corta segmento ante hueco temporal largo', () {
      final raw = [
        _p(lat: -12.0, lng: -77.0, time: DateTime(2026, 7, 30, 10, 0)),
        _p(lat: -12.0005, lng: -77.0, time: DateTime(2026, 7, 30, 10, 20)),
      ];
      final result = filter.filter(raw);
      expect(result.segments.length, 2);
    });

    test('mantiene un solo segmento con movimiento normal', () {
      // ~55 m en 60 s ≈ 3.3 km/h
      final raw = [
        _p(lat: -12.0, lng: -77.0, time: DateTime(2026, 7, 30, 10, 0)),
        _p(lat: -12.0005, lng: -77.0, time: DateTime(2026, 7, 30, 10, 1)),
        _p(lat: -12.0010, lng: -77.0, time: DateTime(2026, 7, 30, 10, 2)),
      ];
      final result = filter.filter(raw);
      expect(result.segments.length, 1);
      expect(result.segments.first.length, 3);
      expect(result.km, greaterThan(0.05));
      expect(result.km, lessThan(0.3));
    });

    test('detecta parada cuando el gestor está quieto varios minutos', () {
      final base = DateTime(2026, 7, 30, 10, 0);
      final raw = [
        _p(lat: -12.0, lng: -77.0, time: base),
        _p(lat: -12.00005, lng: -77.0, time: base.add(const Duration(minutes: 1))),
        _p(lat: -12.00008, lng: -77.0, time: base.add(const Duration(minutes: 2))),
        _p(lat: -12.00002, lng: -77.0, time: base.add(const Duration(minutes: 4))),
      ];
      final result = filter.filter(raw);
      expect(result.stays, isNotEmpty);
      expect(result.stays.first.duration.inMinutes, greaterThanOrEqualTo(3));
    });

    test('km se calcula solo sobre segmentos (sin unir saltos)', () {
      final raw = [
        _p(lat: -12.0, lng: -77.0, time: DateTime(2026, 7, 30, 10, 0)),
        _p(lat: -12.0005, lng: -77.0, time: DateTime(2026, 7, 30, 10, 1)),
        // salto imposible
        _p(lat: -12.2, lng: -77.0, time: DateTime(2026, 7, 30, 10, 1, 5)),
        _p(lat: -12.2005, lng: -77.0, time: DateTime(2026, 7, 30, 10, 2)),
      ];
      final filtered = filter.filter(raw);
      final rawKm = TrackingGeo.trailKm(raw);
      expect(filtered.segments.length, 2);
      expect(filtered.km, lessThan(rawKm));
      expect(filtered.km, lessThan(1));
    });
  });

  group('TrailAnalysis', () {
    final analysis = TrailAnalysis(proximityRadiusMeters: 80);
    final filter = TrailFilter();

    test('clasifica gestionado, pasó cerca y no se acercó', () {
      final base = DateTime(2026, 7, 30, 10, 0);
      // Trail cerca de cliente A (~50 m) y visita a cliente B
      final raw = [
        _p(lat: -12.0, lng: -77.0, time: base),
        _p(
          lat: -12.001,
          lng: -77.0,
          time: base.add(const Duration(minutes: 5)),
          tipo: 'visita',
          cliente: 'Cliente B',
          clienteId: 'b',
          estado: 'visitado_habido',
        ),
        _p(lat: -12.002, lng: -77.0, time: base.add(const Duration(minutes: 10))),
      ];
      final trail = filter.filter(raw);

      final clients = [
        ClientModel(
          id: 'a',
          nombreCompleto: 'Cliente A',
          coordenadaX: -77.0,
          coordenadaY: -12.0004, // ~44 m del primer punto
          estadoGestion: 'pendiente',
        ),
        ClientModel(
          id: 'b',
          nombreCompleto: 'Cliente B',
          coordenadaX: -77.0,
          coordenadaY: -12.001,
          estadoGestion: 'visitado_habido',
          fechaGestion: '2026-07-30',
        ),
        ClientModel(
          id: 'c',
          nombreCompleto: 'Cliente C',
          coordenadaX: -77.05,
          coordenadaY: -12.05, // lejos
          estadoGestion: 'pendiente',
        ),
      ];

      final results = analysis.analyze(trail: trail, clients: clients);
      expect(results.length, 3);

      final byId = {for (final r in results) r.client.id: r};
      expect(byId['b']!.status, ClientTrailStatus.managed);
      expect(byId['a']!.status, ClientTrailStatus.nearbyWithoutVisit);
      expect(byId['c']!.status, ClientTrailStatus.notApproached);
    });

    test('calcula distancia visita ↔ domicilio', () {
      final visit = _p(
        lat: -12.0,
        lng: -77.0,
        tipo: 'visita',
        clienteId: 'x',
      );
      final client = ClientModel(
        id: 'x',
        nombreCompleto: 'X',
        coordenadaX: -77.0,
        coordenadaY: -12.001,
      );
      final d = TrailAnalysis.visitToHomeDistanceMeters(visit, client);
      expect(d, isNotNull);
      expect(d!, greaterThan(100));
      expect(d, lessThan(150));
    });
  });
}
