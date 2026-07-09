import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/client_proximity_sort.dart';

ClientModel _client({
  required String id,
  required String name,
  bool pendiente = true,
  double lat = 0,
  double lng = 0,
}) {
  return ClientModel(
    id: id,
    nombreCompleto: name,
    estadoGestion: pendiente ? 'pendiente' : 'visitado_habido',
    coordenadaX: lng,
    coordenadaY: lat,
  );
}

void main() {
  group('formatDistanceMeters', () {
    test('metros bajo 1 km', () {
      expect(formatDistanceMeters(850), '850 m');
    });

    test('kilómetros con decimal', () {
      expect(formatDistanceMeters(1250), '1.3 km');
    });

    test('kilómetros redondeados largos', () {
      expect(formatDistanceMeters(12500), '13 km');
    });
  });

  group('sortClientsByProximity', () {
    const originLat = -12.0;
    const originLng = -77.0;

    test('pendientes antes que visitados con pendingFirst', () {
      final clients = [
        _client(id: 'v', name: 'Visitado', pendiente: false, lat: -12.001, lng: -77.0),
        _client(id: 'p', name: 'Pendiente', pendiente: true, lat: -12.1, lng: -77.0),
      ];
      final sorted = sortClientsByProximity(
        clients,
        originLat: originLat,
        originLng: originLng,
        pendingFirst: true,
      );
      expect(sorted.first.id, 'p');
      expect(sorted.last.id, 'v');
    });

    test('más cercano primero dentro del mismo estado', () {
      final clients = [
        _client(id: 'far', name: 'Lejos', lat: -12.05, lng: -77.0),
        _client(id: 'near', name: 'Cerca', lat: -12.001, lng: -77.0),
      ];
      final sorted = sortClientsByProximity(
        clients,
        originLat: originLat,
        originLng: originLng,
      );
      expect(sorted.first.id, 'near');
      expect(sorted.last.id, 'far');
    });

    test('sin coordenadas al final', () {
      final clients = [
        _client(id: 'no', name: 'Sin GPS'),
        _client(id: 'yes', name: 'Con GPS', lat: -12.002, lng: -77.0),
      ];
      final sorted = sortClientsByProximity(
        clients,
        originLat: originLat,
        originLng: originLng,
      );
      expect(sorted.first.id, 'yes');
      expect(sorted.last.id, 'no');
    });
  });

  group('distanceLabelForClient', () {
    test('null sin origen', () {
      final c = _client(id: 'a', name: 'A', lat: -12.001, lng: -77.0);
      expect(distanceLabelForClient(c, null, null), isNull);
    });

    test('etiqueta con origen y coords', () {
      final c = _client(id: 'a', name: 'A', lat: -12.001, lng: -77.0);
      final label = distanceLabelForClient(c, -12.0, -77.0);
      expect(label, isNotNull);
      expect(label, contains('m'));
    });
  });
}
