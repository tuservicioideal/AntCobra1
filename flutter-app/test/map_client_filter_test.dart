import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/map_client_filter.dart';

ClientModel _client({
  required String id,
  String seccionKey = '01_1211_H',
  String campanaBanco = '202607',
  String nombre = '',
}) {
  return ClientModel(
    id: id,
    nombreCompleto: nombre.isEmpty ? 'Cliente $id' : nombre,
    seccionKey: seccionKey,
    campanaBanco: campanaBanco,
    estadoGestion: 'pendiente',
  );
}

void main() {
  group('filterMapClientList', () {
    final clients = [
      _client(id: 'a', seccionKey: '01_1211_H', nombre: 'Maria Torres'),
      _client(id: 'b', seccionKey: '01_1211_J', nombre: 'Karina Renteria'),
      _client(
        id: 'c',
        seccionKey: '01_1211_H',
        campanaBanco: '202606',
        nombre: 'Ana Perez',
      ),
    ];

    test('gestor de campo no ve cartera: filtra por sección entre enviados', () {
      final visible = filterMapClientList(
        clients: clients,
        campanaFilter: null,
        query: '',
        restrictToProfileCandidates: true,
        selectedSection: '01_1211_H',
        allSectionsKey: '__all_my_sections__',
      );

      expect(visible.map((c) => c.id), ['a', 'c']);
    });

    test('todas las secciones del gestor conservan los enviados', () {
      final visible = filterMapClientList(
        clients: clients,
        campanaFilter: null,
        query: '',
        restrictToProfileCandidates: true,
        selectedSection: '__all_my_sections__',
        allSectionsKey: '__all_my_sections__',
      );

      expect(visible.map((c) => c.id), ['a', 'b', 'c']);
    });

    test('sin restrictToProfileCandidates y con ids, solo candidatos', () {
      final visible = filterMapClientList(
        clients: clients,
        campanaFilter: null,
        query: '',
        restrictToProfileCandidates: false,
        candidateIds: {'b'},
      );

      expect(visible.map((c) => c.id), ['b']);
    });

    test('búsqueda por nombre sobre el lote enviado', () {
      final visible = filterMapClientList(
        clients: clients,
        campanaFilter: null,
        query: 'karina',
        restrictToProfileCandidates: true,
      );

      expect(visible.map((c) => c.id), ['b']);
    });

    test('filtra por etapa E2', () {
      final withTramo = [
        _client(id: 'a'),
        ClientModel(
          id: 'e2',
          nombreCompleto: 'Etapa dos',
          seccionKey: '01_1211_H',
          campanaBanco: '202607',
          estadoGestion: 'pendiente',
          tramoActual: 2,
        ),
      ];
      final visible = filterMapClientList(
        clients: withTramo,
        campanaFilter: null,
        query: '',
        restrictToProfileCandidates: false,
        tramoFilter: {2},
      );

      expect(visible.map((c) => c.id), ['e2']);
    });

    test('sin enviados desde Perfil no muestra cartera ajena', () {
      final visible = filterMapClientList(
        clients: const [],
        campanaFilter: null,
        query: '',
        restrictToProfileCandidates: true,
      );

      expect(visible, isEmpty);
    });
  });
}
