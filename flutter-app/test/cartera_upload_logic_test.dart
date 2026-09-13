import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/models/cartera_job_model.dart';
import 'package:app_recaudo_legal/utils/cartera_upload_logic.dart';

void main() {
  group('validateExcelFileName', () {
    test('accepts xlsx and xlsm', () {
      expect(validateExcelFileName('banco.xlsx'), isNull);
      expect(validateExcelFileName('banco.XLSM'), isNull);
    });

    test('rejects other extensions', () {
      expect(validateExcelFileName('banco.csv'), isNotNull);
      expect(validateExcelFileName('banco.xls'), isNotNull);
    });
  });

  group('canConfirmPublish', () {
    test('requires preview with clients', () {
      expect(
        canConfirmPublish(
          estado: 'parseando',
          totalClientes: 10,
          seccionesSinGestor: const [],
          forceSinGestor: false,
        ),
        isFalse,
      );
      expect(
        canConfirmPublish(
          estado: 'preview',
          totalClientes: 0,
          seccionesSinGestor: const [],
          forceSinGestor: false,
        ),
        isFalse,
      );
      expect(
        canConfirmPublish(
          estado: 'preview',
          totalClientes: 12,
          seccionesSinGestor: const [],
          forceSinGestor: false,
        ),
        isTrue,
      );
    });

    test('blocks missing gestores unless forced', () {
      expect(
        canConfirmPublish(
          estado: 'preview',
          totalClientes: 12,
          seccionesSinGestor: const ['01_1211_A'],
          forceSinGestor: false,
        ),
        isFalse,
      );
      expect(
        canConfirmPublish(
          estado: 'preview',
          totalClientes: 12,
          seccionesSinGestor: const ['01_1211_A'],
          forceSinGestor: true,
        ),
        isTrue,
      );
    });
  });

  test('CarteraJob.fromMap reads nested preview fields', () {
    final job = CarteraJob.fromMap('j1', {
      'estado': 'preview',
      'archivo': {'nombre': '01.xlsx'},
      'resumen': {'total_clientes': 12, 'total_secciones': 4},
      'diff': {'nuevos': 2, 'removidos': 1, 'actualizados': 3},
      'secciones_sin_gestor': ['01_1211_A'],
      'muestras': {
        'nuevos': [
          {
            'codigo_cliente': 'N1',
            'nombre_completo': 'Nuevo',
            'seccion_key': '01_1211_H',
          }
        ],
      },
    });
    expect(job.estado, 'preview');
    expect(job.archivoNombre, '01.xlsx');
    expect(job.resumen.totalClientes, 12);
    expect(job.diff.removidos, 1);
    expect(job.seccionesSinGestor, ['01_1211_A']);
    expect(job.nuevos.single.codigoCliente, 'N1');
    expect(job.parsedPath, isEmpty);
  });

  test('CarteraJob.fromMap reads creado_at DateTime', () {
    final job = CarteraJob.fromMap('j2', {
      'estado': 'listo',
      'creado_at': DateTime.utc(2026, 9, 1, 13, 10),
    });
    expect(job.creadoAt, DateTime.utc(2026, 9, 1, 13, 10));
  });

  test('shouldWarnLargeFile only on mobile', () {
    expect(shouldWarnLargeFile(isWeb: true, bytes: 20 * 1024 * 1024), isFalse);
    expect(shouldWarnLargeFile(isWeb: false, bytes: 20 * 1024 * 1024), isTrue);
    expect(shouldWarnLargeFile(isWeb: false, bytes: 1024), isFalse);
  });
}
