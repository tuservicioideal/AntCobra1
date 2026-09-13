import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/services/doxeo_queue_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DoxeoComando.previewMessage', () {
    test('Solo DNI cuando la plantilla está vacía', () {
      const cmd = DoxeoComando(id: 'x', nombre: 'Solo');
      expect(cmd.previewMessage('12345678'), '12345678');
    });

    test('sustituye {dni} en la plantilla', () {
      const cmd = DoxeoComando(
        id: 'reniec',
        nombre: 'RENIEC',
        plantilla: '/reniec {dni}',
      );
      expect(cmd.previewMessage('87654321'), '/reniec 87654321');
    });

    test('antepone la plantilla si no tiene {dni}', () {
      const cmd = DoxeoComando(
        id: 'dni',
        nombre: 'DNI',
        plantilla: '/dni',
      );
      expect(cmd.previewMessage('11223344'), '/dni 11223344');
    });
  });

  group('resolverComando', () {
    const dni = DoxeoComando(id: 'dni', nombre: 'DNI', plantilla: '/dni');
    const seeker =
        DoxeoComando(id: 'seeker', nombre: 'seeker', plantilla: '/seeker');
    const arbol = DoxeoComando(
      id: 'arbol',
      nombre: 'Árbol genealógico',
      plantilla: '/arbol',
    );
    const comandos = [dni, seeker, arbol];

    test('usa el primero si no hay selección (nunca Solo DNI)', () {
      final elegido = resolverComando(comandos, '');
      expect(elegido, isNotNull);
      expect(elegido!.id, 'dni');
      expect(elegido.nombre, isNot(equals('Solo DNI')));
    });

    test('respeta DNI, seeker o árbol cuando el id coincide', () {
      expect(resolverComando(comandos, 'seeker')!.nombre, 'seeker');
      expect(resolverComando(comandos, 'arbol')!.nombre, 'Árbol genealógico');
      expect(resolverComando(comandos, 'dni')!.nombre, 'DNI');
    });

    test('sin comandos no hay consulta', () {
      expect(resolverComando(const [], ''), isNull);
    });
  });

  group('DoxeoJob.fromMap', () {
    test('lee resultado parseado e imágenes', () {
      final job = DoxeoJob.fromMap('job1', {
        'dni': '12345678',
        'comando_nombre': 'RENIEC',
        'mensaje': '/reniec 12345678',
        'estado': 'completado',
        'resultado': {
          'parsed': {
            'nombre': 'PEREZ',
            'phones': ['+51999999999'],
            'addresses': ['Av. Lima 1'],
            'distrito': 'Lima',
            'provincia': 'Lima',
            'departamento': 'Lima',
          },
          'raw': 'Nombre: PEREZ',
          'imagenes': ['doxeo_jobs/job1/img_0.jpg'],
          'has_data': true,
        },
      });
      expect(job.isDone, isTrue);
      expect(job.canRetry, isFalse);
      expect(job.nombre, 'PEREZ');
      expect(job.phones, ['+51999999999']);
      expect(job.addresses, ['Av. Lima 1']);
      expect(job.ubicacionTexto, 'Lima, Lima, Lima');
      expect(job.imagenes, ['doxeo_jobs/job1/img_0.jpg']);
      expect(job.hasData, isTrue);
      expect(job.archivos, isEmpty);
    });

    test('lee archivos PDF del resultado', () {
      final job = DoxeoJob.fromMap('job-pdf', {
        'dni': '12345678',
        'estado': 'completado',
        'resultado': {
          'parsed': <String, dynamic>{},
          'raw': '[pdf]',
          'imagenes': <String>[],
          'archivos': [
            {
              'path': 'doxeo_jobs/job-pdf/doc_0.pdf',
              'file_name': 'ficha.pdf',
              'mime_type': 'application/pdf',
            },
          ],
          'has_data': true,
        },
      });
      expect(job.archivos, hasLength(1));
      expect(job.archivos.first.path, 'doxeo_jobs/job-pdf/doc_0.pdf');
      expect(job.archivos.first.fileName, 'ficha.pdf');
      expect(job.archivos.first.mimeType, 'application/pdf');
      expect(job.tieneContenidoUtil, isTrue);
      expect(
        job.toConsultaGuardadaMap()['resultado']['archivos'],
        [
          {
            'path': 'doxeo_jobs/job-pdf/doc_0.pdf',
            'file_name': 'ficha.pdf',
            'mime_type': 'application/pdf',
          },
        ],
      );
    });

    test('tieneContenidoUtil con PDF aunque has_data sea false', () {
      final job = DoxeoJob.fromMap('x', {
        'estado': 'completado',
        'resultado': {
          'has_data': false,
          'archivos': [
            {'path': 'doxeo_jobs/x/doc_0.pdf', 'file_name': 'a.pdf'},
          ],
        },
      });
      expect(job.hasData, isFalse);
      expect(job.tieneContenidoUtil, isTrue);
    });

    test('timeout y error permiten reintento', () {
      expect(
        DoxeoJob.fromMap('a', {'estado': 'timeout'}).canRetry,
        isTrue,
      );
      expect(
        DoxeoJob.fromMap('b', {'estado': 'error'}).canRetry,
        isTrue,
      );
      expect(
        DoxeoJob.fromMap('c', {'estado': 'pendiente'}).isPending,
        isTrue,
      );
    });
  });

  group('DoxeoWorker.online', () {
    test('online si el heartbeat tiene menos de 90 s', () {
      final worker = DoxeoWorker(
        id: 'pc1',
        telegramOk: true,
        ultimoSeen: DateTime.now().subtract(const Duration(seconds: 20)),
      );
      expect(worker.online, isTrue);
    });

    test('offline si el heartbeat es viejo', () {
      final worker = DoxeoWorker(
        id: 'pc1',
        telegramOk: true,
        ultimoSeen: DateTime.now().subtract(const Duration(minutes: 5)),
      );
      expect(worker.online, isFalse);
    });
  });

  group('normalizarDocumento', () {
    test('quita los ceros de relleno del Excel del banco', () {
      expect(normalizarDocumento('0047808409'), '47808409');
      expect(normalizarDocumento('0002820743'), '02820743');
      expect(normalizarDocumento(' 0072778487 '), '72778487');
    });

    test('respeta documentos de 8 dígitos y CE más largos', () {
      expect(normalizarDocumento('47808409'), '47808409');
      expect(normalizarDocumento('02820743'), '02820743');
      expect(normalizarDocumento('776968822'), '776968822');
      expect(normalizarDocumento('1234567890'), '1234567890');
    });

    test('no toca documentos con letras', () {
      expect(normalizarDocumento('A123456B'), 'A123456B');
    });

    test('el preview encolable usa el documento limpio', () {
      const cmd = DoxeoComando(id: 'dni', nombre: 'DNI', plantilla: '/dni');
      expect(
        cmd.previewMessage(normalizarDocumento('0002820743')),
        '/dni 02820743',
      );
    });
  });

  group('consultas guardadas por cliente', () {
    test('la clave vacía es _dni y no admite puntos', () {
      expect(doxeoConsultaKey(''), '_dni');
      expect(doxeoConsultaKey('  '), '_dni');
      expect(doxeoConsultaKey('abc.def'), 'abc_def');
      expect(doxeoConsultaKey('reniec'), 'reniec');
    });

    test('solo se persisten consultas terminadas (no canceladas ni en curso)', () {
      expect(debePersistirConsulta('completado'), isTrue);
      expect(debePersistirConsulta('timeout'), isTrue);
      expect(debePersistirConsulta('error'), isTrue);
      expect(debePersistirConsulta('cancelado'), isFalse);
      expect(debePersistirConsulta('pendiente'), isFalse);
      expect(debePersistirConsulta('en_proceso'), isFalse);
    });

    test('no guarda en clientes libres ni sin ruta Firestore', () {
      expect(
        puedeGuardarConsultaEnCliente(ClientModel(
          id: 'c1',
          campaignId: 'camp',
          seccionKey: 'LIMA',
        )),
        isTrue,
      );
      expect(
        puedeGuardarConsultaEnCliente(ClientModel(
          id: 'libre_123',
          campaignId: 'camp',
          seccionKey: 'LIMA',
        )),
        isFalse,
      );
      expect(
        puedeGuardarConsultaEnCliente(ClientModel(id: 'c1')),
        isFalse,
      );
    });

    test('una consulta nueva del mismo tipo reemplaza la anterior', () {
      final vieja = DoxeoJob(
        id: 'old',
        comandoId: 'reniec',
        comandoNombre: 'RENIEC',
        estado: 'completado',
        creadoAt: DateTime(2026, 9, 1, 10),
        parsed: const {'nombre': 'VIEJO'},
        hasData: true,
      );
      final nueva = DoxeoJob(
        id: 'new',
        comandoId: 'reniec',
        comandoNombre: 'RENIEC',
        estado: 'completado',
        creadoAt: DateTime(2026, 9, 10, 18),
        parsed: const {'nombre': 'NUEVO'},
        hasData: true,
      );
      final otra = DoxeoJob(
        id: 'dni1',
        comandoId: '',
        comandoNombre: 'Solo DNI',
        estado: 'completado',
        creadoAt: DateTime(2026, 9, 8),
        parsed: const {'nombre': 'DNI'},
        hasData: true,
      );
      final ultimas = ultimasConsultasPorTipo([vieja, otra, nueva]);
      expect(ultimas.length, 2);
      expect(ultimas.firstWhere((j) => j.comandoId == 'reniec').id, 'new');
      expect(ultimas.firstWhere((j) => j.comandoId == 'reniec').nombre, 'NUEVO');
      expect(ultimas.any((j) => j.comandoId.isEmpty), isTrue);
    });

    test('lee el mapa guardado en el documento del cliente', () {
      final jobs = parseDoxeoConsultas({
        '_dni': {
          'job_id': 'j1',
          'comando_id': '',
          'comando_nombre': 'Solo DNI',
          'estado': 'completado',
          'dni': '12345678',
          'mensaje': '12345678',
          'actualizado_at': DateTime(2026, 9, 10, 12),
          'resultado': {
            'parsed': {'nombre': 'PEREZ', 'phones': ['999']},
            'raw': 'Nombre: PEREZ',
            'imagenes': <String>[],
            'has_data': true,
          },
        },
        'reniec': {
          'job_id': 'j2',
          'comando_id': 'reniec',
          'comando_nombre': 'RENIEC',
          'estado': 'completado',
          'dni': '12345678',
          'resultado': {
            'parsed': {'nombre': 'PEREZ RENIEC'},
            'has_data': true,
          },
        },
      });
      expect(jobs.length, 2);
      final dni = jobs.firstWhere((j) => j.comandoId.isEmpty);
      expect(dni.nombre, 'PEREZ');
      expect(dni.phones, ['999']);
      expect(jobs.firstWhere((j) => j.comandoId == 'reniec').nombre, 'PEREZ RENIEC');
    });

    test('ClientModel conserva doxeo_consultas al leer Firestore', () {
      final client = ClientModel.fromMap('c1', {
        'nombre_completo': 'PEREZ',
        'doxeo_consultas': {
          'reniec': {
            'job_id': 'j2',
            'comando_id': 'reniec',
            'comando_nombre': 'RENIEC',
            'estado': 'completado',
            'resultado': {
              'parsed': {'nombre': 'PEREZ RENIEC'},
              'has_data': true,
            },
          },
        },
      }, campaignId: 'camp');
      final jobs = parseDoxeoConsultas(client.doxeoConsultasRaw);
      expect(jobs.single.nombre, 'PEREZ RENIEC');
    });
  });
}
