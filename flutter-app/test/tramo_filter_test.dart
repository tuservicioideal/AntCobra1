import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/tramo_filter.dart';

ClientModel _client({
  required String id,
  int tramo = 1,
}) {
  return ClientModel(
    id: id,
    nombreCompleto: 'Cliente $id',
    tramoActual: tramo,
    estadoGestion: 'pendiente',
    activoEnCartera: true,
    estadoCiclo: 'activa',
  );
}

void main() {
  group('effectiveTramo / tramoLabel', () {
    test('0 o negativo se tratan como etapa 1', () {
      expect(effectiveTramo(_client(id: 'a', tramo: 0)), 1);
      expect(effectiveTramo(_client(id: 'b', tramo: -2)), 1);
      expect(tramoLabel(0), 'E1');
    });

    test('3 o más se tratan como etapa 3', () {
      expect(effectiveTramo(_client(id: 'a', tramo: 3)), 3);
      expect(effectiveTramo(_client(id: 'b', tramo: 5)), 3);
      expect(tramoLabel(4), 'E3');
    });

    test('etiquetas cortas', () {
      expect(tramoLabel(1), 'E1');
      expect(tramoLabel(2), 'E2');
      expect(tramoLabel(3), 'E3');
    });
  });

  group('matchesTramoFilter / applyTramoFilter', () {
    final clients = [
      _client(id: 'e1', tramo: 1),
      _client(id: 'e1z', tramo: 0),
      _client(id: 'e2', tramo: 2),
      _client(id: 'e3', tramo: 3),
      _client(id: 'e3plus', tramo: 4),
    ];

    test('sin selección deja pasar todos', () {
      expect(applyTramoFilter(clients, {}).map((c) => c.id).toList(),
          ['e1', 'e1z', 'e2', 'e3', 'e3plus']);
    });

    test('E1 incluye tramo 0', () {
      expect(
        applyTramoFilter(clients, {1}).map((c) => c.id).toList(),
        ['e1', 'e1z'],
      );
    });

    test('E2 solo tramo 2', () {
      expect(
        applyTramoFilter(clients, {2}).map((c) => c.id).toList(),
        ['e2'],
      );
    });

    test('E3 incluye tramo >= 3', () {
      expect(
        applyTramoFilter(clients, {3}).map((c) => c.id).toList(),
        ['e3', 'e3plus'],
      );
    });
  });

  group('toggleExclusiveTramo', () {
    test('selecciona la etapa tocada', () {
      expect(toggleExclusiveTramo({}, 2), {2});
    });

    test('el mismo toque quita el filtro', () {
      expect(toggleExclusiveTramo({1}, 1), isEmpty);
    });

    test('cambiar de etapa reemplaza la anterior', () {
      expect(toggleExclusiveTramo({1}, 3), {3});
    });
  });

  group('countByTramo', () {
    test('agrupa 0 en E1 y >=3 en E3', () {
      final counts = countByTramo([
        _client(id: 'a', tramo: 0),
        _client(id: 'b', tramo: 1),
        _client(id: 'c', tramo: 2),
        _client(id: 'd', tramo: 4),
      ]);
      expect(counts[1], 2);
      expect(counts[2], 1);
      expect(counts[3], 1);
    });
  });

  test('tramoFilterCacheKey es estable', () {
    expect(tramoFilterCacheKey({}), '');
    expect(tramoFilterCacheKey({3, 1}), '1,3');
  });
}
