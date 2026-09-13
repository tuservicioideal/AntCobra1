import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/bitacora_campo_entry.dart';
import 'package:app_recaudo_legal/services/bitacora_campo_service.dart';

void main() {
  group('BitacoraCampoEntry IDs', () {
    test('ids deterministas', () {
      expect(BitacoraCampoEntry.idUbicacion('abc'), 'ubicacion_abc');
      expect(BitacoraCampoEntry.idTelegram('job1'), 'telegram_job1');
      expect(BitacoraCampoEntry.idNotaCampo('h1'), 'nota_campo_h1');
      expect(BitacoraCampoEntry.idNotaGestion('v1'), 'nota_gestion_v1');
    });
  });

  group('BitacoraCampoEntry.fromMap', () {
    test('mapea campos y payload', () {
      final e = BitacoraCampoEntry.fromMap('ubicacion_x', {
        'tipo': 'ubicacion',
        'fecha_dia': '2026-09-10',
        'campaign_id': 'c1',
        'seccion_key': 's1',
        'cliente_id': 'cli1',
        'cliente_nombre': 'Pérez',
        'codigo_cliente': 'C-1',
        'dni': '12345678',
        'usuario_uid': 'u1',
        'usuario_nombre': 'Gestor',
        'usuario_rol': 'gestor',
        'resumen': 'GPS verificado',
        'origen_id': 'x',
        'origen_coleccion': 'historial_contacto',
        'payload': {'lat': -12.1, 'lng': -77.0},
        'creado_at': '2026-09-10T15:00:00.000',
      });
      expect(e.isUbicacion, isTrue);
      expect(e.displayType, 'Ubicación GPS');
      expect(e.clienteNombre, 'Pérez');
      expect(e.payload['lat'], -12.1);
      expect(e.hasCliente, isTrue);
    });

    test('isNota agrupa campo y gestión', () {
      expect(
        const BitacoraCampoEntry(tipo: 'nota_campo').isNota,
        isTrue,
      );
      expect(
        const BitacoraCampoEntry(tipo: 'nota_gestion').isNota,
        isTrue,
      );
      expect(
        const BitacoraCampoEntry(tipo: 'telegram').isNota,
        isFalse,
      );
    });
  });

  group('matchesLocalQuery', () {
    const sample = BitacoraCampoEntry(
      clienteNombre: 'Juan Pérez',
      codigoCliente: 'AB-99',
      dni: '47808409',
      resumen: 'GPS verificado: -12.05, -77.04',
      usuarioNombre: 'Ana',
    );

    test('match por nombre y dni', () {
      expect(BitacoraCampoEntry.matchesLocalQuery(sample, 'pérez'), isTrue);
      expect(BitacoraCampoEntry.matchesLocalQuery(sample, '4780'), isTrue);
      expect(BitacoraCampoEntry.matchesLocalQuery(sample, 'AB-99'), isTrue);
      expect(BitacoraCampoEntry.matchesLocalQuery(sample, 'xyz'), isFalse);
      expect(BitacoraCampoEntry.matchesLocalQuery(sample, ''), isTrue);
    });
  });

  group('BitacoraCampoService.buildEventMap', () {
    test('incluye campos mínimos y fecha_dia', () {
      final when = DateTime(2026, 9, 10, 18, 30);
      final map = BitacoraCampoService.buildEventMap(
        tipo: BitacoraCampoEntry.tipoTelegram,
        when: when,
        campaignId: 'c',
        seccionKey: 's',
        clienteId: 'id',
        clienteNombre: 'N',
        codigoCliente: 'cod',
        dni: '123',
        usuarioUid: 'u',
        usuarioNombre: 'U',
        usuarioRol: 'gestor',
        resumen: 'ok',
        origenId: 'job',
        origenColeccion: 'doxeo_jobs',
        payload: {'job_id': 'job'},
      );
      expect(map['tipo'], 'telegram');
      expect(map['fecha_dia'], '2026-09-10');
      expect(map['payload'], {'job_id': 'job'});
      expect(map.keys, containsAll([
        'tipo',
        'creado_at',
        'fecha_dia',
        'campaign_id',
        'seccion_key',
        'cliente_id',
        'cliente_nombre',
        'codigo_cliente',
        'dni',
        'usuario_uid',
        'usuario_nombre',
        'usuario_rol',
        'resumen',
        'origen_id',
        'origen_coleccion',
        'payload',
      ]));
    });
  });

  test('formatFechaDia', () {
    expect(
      BitacoraCampoService.formatFechaDia(DateTime(2026, 1, 5)),
      '2026-01-05',
    );
  });
}
