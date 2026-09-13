import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/cierre_filter.dart';

ClientModel _client({
  String id = '1',
  String fechaCierre = '',
  String fechaCierreDt = '',
  String fechaAsignacion = '',
}) {
  return ClientModel(
    id: id,
    nombreCompleto: 'Test $id',
    fechaCierre: fechaCierre,
    fechaCierreDt: fechaCierreDt,
    fechaAsignacion: fechaAsignacion,
    estadoGestion: 'pendiente',
    activoEnCartera: true,
    estadoCiclo: 'activa',
  );
}

void main() {
  final now = DateTime(2026, 9, 15);

  group('resolveFechaCierre', () {
    test('prioriza fecha_cierre_dt ISO', () {
      final c = _client(
        fechaCierreDt: '2026-10-01',
        fechaCierre: '20/09/2026',
      );
      expect(resolveFechaCierre(c), DateTime(2026, 10, 1));
    });

    test('usa fecha_cierre dd/MM/yyyy', () {
      final c = _client(fechaCierre: '20/09/2026');
      expect(resolveFechaCierre(c), DateTime(2026, 9, 20));
    });

    test('fallback: asignación + duracion - 1', () {
      final c = _client(fechaAsignacion: '2026-08-01');
      expect(
        resolveFechaCierre(c, duracionDias: 59),
        DateTime(2026, 8, 1).add(const Duration(days: 58)),
      );
    });

    test('sin fecha retorna null', () {
      expect(resolveFechaCierre(_client()), isNull);
    });
  });

  group('diasParaCerrar', () {
    test('positivo = faltan días', () {
      final c = _client(fechaCierre: '20/09/2026');
      expect(diasParaCerrar(c, now: now), 5);
    });

    test('cero = hoy', () {
      final c = _client(fechaCierre: '15/09/2026');
      expect(diasParaCerrar(c, now: now), 0);
    });

    test('negativo = vencido', () {
      final c = _client(fechaCierre: '10/09/2026');
      expect(diasParaCerrar(c, now: now), -5);
    });
  });

  group('matchesCierreFilter / applyCierreFilter', () {
    final clients = [
      _client(id: 'hoy', fechaCierre: '15/09/2026'),
      _client(id: 'd3', fechaCierre: '18/09/2026'),
      _client(id: 'd7', fechaCierre: '22/09/2026'),
      _client(id: 'd15', fechaCierre: '30/09/2026'),
      _client(id: 'vencido', fechaCierre: '10/09/2026'),
      _client(id: 'sin', fechaCierre: ''),
    ];

    test('none deja pasar todos', () {
      expect(
        applyCierreFilter(clients, CierreFilter.none, now: now).length,
        clients.length,
      );
    });

    test('Hoy: solo dias == 0', () {
      final f = CierreFilter.withinDays(0);
      final r = applyCierreFilter(clients, f, now: now);
      expect(r.map((c) => c.id), ['hoy']);
    });

    test('≤3 incluye hoy y d3', () {
      final f = CierreFilter.withinDays(3);
      final r = applyCierreFilter(clients, f, now: now);
      expect(r.map((c) => c.id).toList()..sort(), ['d3', 'hoy']);
    });

    test('≤7 no incluye d15 ni vencidos', () {
      final f = CierreFilter.withinDays(7);
      final ids = applyCierreFilter(clients, f, now: now).map((c) => c.id);
      expect(ids, containsAll(['hoy', 'd3', 'd7']));
      expect(ids, isNot(contains('d15')));
      expect(ids, isNot(contains('vencido')));
      expect(ids, isNot(contains('sin')));
    });

    test('vencidos', () {
      final f = CierreFilter.onlyVencidos();
      final r = applyCierreFilter(clients, f, now: now);
      expect(r.map((c) => c.id), ['vencido']);
    });

    test('rango de fechas', () {
      final f = CierreFilter.byDateRange(
        from: DateTime(2026, 9, 18),
        to: DateTime(2026, 9, 22),
      );
      final ids = applyCierreFilter(clients, f, now: now).map((c) => c.id);
      expect(ids, containsAll(['d3', 'd7']));
      expect(ids, isNot(contains('hoy')));
    });

    test('un solo día', () {
      final f = CierreFilter.bySingleDate(DateTime(2026, 9, 18));
      final r = applyCierreFilter(clients, f, now: now);
      expect(r.map((c) => c.id), ['d3']);
    });

    test('sin fecha queda fuera del filtro activo', () {
      final f = CierreFilter.withinDays(60);
      expect(
        matchesCierreFilter(_client(id: 'sin'), f, now: now),
        isFalse,
      );
    });
  });

  group('cierreFilterLabel / cacheKey', () {
    test('labels', () {
      expect(cierreFilterLabel(CierreFilter.none), 'Cierre');
      expect(cierreFilterLabel(CierreFilter.withinDays(0)), 'Hoy');
      expect(cierreFilterLabel(CierreFilter.withinDays(7)), '≤7 días');
      expect(cierreFilterLabel(CierreFilter.onlyVencidos()), 'Vencidos');
      expect(
        cierreFilterLabel(CierreFilter.bySingleDate(DateTime(2026, 9, 15))),
        '15/09',
      );
    });

    test('cacheKey estable', () {
      expect(CierreFilter.none.cacheKey, '');
      expect(CierreFilter.withinDays(7).cacheKey, 'days:7');
      expect(CierreFilter.onlyVencidos().cacheKey, 'days:vencidos');
      expect(
        CierreFilter.bySingleDate(DateTime(2026, 9, 15)).cacheKey,
        'date:2026-09-15:2026-09-15',
      );
    });
  });

  group('formatCierreBadge / urgency', () {
    test('badge textos', () {
      expect(
        formatCierreBadge(cierre: DateTime(2026, 9, 20), now: now),
        '20/09 · 5d',
      );
      expect(
        formatCierreBadge(cierre: DateTime(2026, 9, 15), now: now),
        'Hoy',
      );
      expect(
        formatCierreBadge(cierre: DateTime(2026, 9, 10), now: now),
        'Vencido',
      );
      expect(formatCierreBadge(cierre: null, now: now), '');
    });

    test('urgency levels', () {
      expect(
        cierreUrgencyLevel(cierre: DateTime(2026, 9, 10), now: now),
        3,
      );
      expect(
        cierreUrgencyLevel(cierre: DateTime(2026, 9, 15), now: now),
        2,
      );
      expect(
        cierreUrgencyLevel(cierre: DateTime(2026, 9, 20), now: now),
        1,
      );
      expect(
        cierreUrgencyLevel(cierre: DateTime(2026, 10, 1), now: now),
        0,
      );
    });
  });

  group('sortClientsByCierre', () {
    test('más urgente primero; sin fecha al final', () {
      final list = [
        _client(id: 'b', fechaCierre: '20/09/2026'),
        _client(id: 'a', fechaCierre: '16/09/2026'),
        _client(id: 'sin'),
        _client(id: 'v', fechaCierre: '10/09/2026'),
      ];
      final sorted = sortClientsByCierre(list);
      expect(sorted.map((c) => c.id), ['v', 'a', 'b', 'sin']);
    });
  });
}
