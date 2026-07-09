import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/campana_banco_utils.dart';

ClientModel _client({String campanaBanco = '', bool active = true}) {
  return ClientModel(
    id: '1',
    nombreCompleto: 'Test',
    campanaBanco: campanaBanco,
    estadoGestion: 'pendiente',
    activoEnCartera: active,
    estadoCiclo: active ? 'activa' : 'cerrada',
  );
}

void main() {
  group('distinctCampanaBancoValues', () {
    test('ordena valores y agrega Sin campaña si hay vacíos', () {
      final values = distinctCampanaBancoValues([
        _client(campanaBanco: 'BANCO-2026-02'),
        _client(campanaBanco: 'BANCO-2026-01'),
        _client(campanaBanco: ''),
        _client(campanaBanco: 'BANCO-2026-01'),
      ]);

      expect(values, [
        'BANCO-2026-01',
        'BANCO-2026-02',
        kSinCampanaBancoKey,
      ]);
    });

    test('ignora clientes inactivos para el gestor', () {
      final values = distinctCampanaBancoValues([
        _client(campanaBanco: 'BANCO-2026-01'),
        _client(campanaBanco: 'BANCO-2026-99', active: false),
      ]);

      expect(values, ['BANCO-2026-01']);
    });
  });

  group('applyCampanaBancoFilter', () {
    final clients = [
      _client(campanaBanco: 'A'),
      _client(campanaBanco: 'B'),
      _client(campanaBanco: ''),
    ];

    test('null devuelve todos', () {
      expect(applyCampanaBancoFilter(clients, null).length, 3);
    });

    test('filtra por valor exacto', () {
      final filtered = applyCampanaBancoFilter(clients, 'B');
      expect(filtered.length, 1);
      expect(filtered.first.campanaBanco, 'B');
    });

    test('filtra sin campaña', () {
      final filtered = applyCampanaBancoFilter(clients, kSinCampanaBancoKey);
      expect(filtered.length, 1);
      expect(filtered.first.campanaBanco, '');
    });
  });

  group('campanaBancoFilterBarVisible', () {
    test('oculta si solo hay una campaña con valor', () {
      expect(campanaBancoFilterBarVisible(['202516']), isFalse);
    });

    test('muestra si hay dos campañas', () {
      expect(campanaBancoFilterBarVisible(['202516', '202610']), isTrue);
    });

    test('muestra si solo hay clientes sin campaña', () {
      expect(campanaBancoFilterBarVisible([kSinCampanaBancoKey]), isTrue);
    });
  });

  group('campanaBancoFilterLabel', () {
    test('etiquetas legibles', () {
      expect(campanaBancoFilterLabel(null), 'Todas las campañas');
      expect(campanaBancoFilterLabel(kSinCampanaBancoKey), kSinCampanaBancoLabel);
      expect(campanaBancoFilterLabel('202516'), '202516');
    });
  });
}
