import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/phone_contact_launcher.dart';
import 'package:app_recaudo_legal/utils/whatsapp_plantilla_renderer.dart';
import 'package:flutter_test/flutter_test.dart';

ClientModel _client({
  String nombre = 'Ana López',
  String dni = '87654321',
  String codigo = 'C-99',
  double deuda = 1500.5,
  int dias = 30,
  int tramo = 2,
  String direccion = 'Calle 1',
  String distrito = 'Comas',
  String telefono = '912345678',
}) {
  return ClientModel(
    id: '1',
    nombreCompleto: nombre,
    numeroDocumento: dni,
    codigoCliente: codigo,
    importeDeudaPendiente: deuda,
    diasAtraso: dias,
    tramoActual: tramo,
    direccion: direccion,
    distrito: distrito,
    telefonoMovil: telefono,
  );
}

void main() {
  group('buildWhatsAppPlaceholderMap', () {
    test('incluye nombre, deuda y gestor', () {
      final map = buildWhatsAppPlaceholderMap(
        client: _client(),
        gestorNombre: 'Pedro',
      );
      expect(map['nombre'], 'Ana López');
      expect(map['dni'], '87654321');
      expect(map['deuda'], contains('S/'));
      expect(map['deuda'], contains('1.500,50'));
      expect(map['dias_atraso'], '30');
      expect(map['tramo'], '2');
      expect(map['gestor'], 'Pedro');
    });

    test('vacíos usan estimado/a o guión', () {
      final map = buildWhatsAppPlaceholderMap(
        client: _client(
          nombre: '',
          dni: '',
          codigo: '',
          deuda: 0,
          dias: 0,
          tramo: 0,
          direccion: '',
          distrito: '',
          telefono: '',
        ),
      );
      expect(map['nombre'], 'estimado/a');
      expect(map['dni'], '—');
      expect(map['deuda'], '—');
      expect(map['dias_atraso'], '—');
      expect(map['gestor'], '—');
    });
  });

  group('renderWhatsAppPlantilla', () {
    test('sustituye todas las variables', () {
      final text = renderWhatsAppPlantilla(
        'Hola {nombre}, DNI {dni}, debe {deuda}. Soy {gestor}.',
        values: sampleWhatsAppPlaceholders(),
      );
      expect(text, contains('Juan Pérez'));
      expect(text, contains('12345678'));
      expect(text, contains('S/ 1.234,56'));
      expect(text, contains('María Gestora'));
      expect(text, isNot(contains('{nombre}')));
    });

    test('clave desconocida o vacía → guión', () {
      final text = renderWhatsAppPlantilla(
        'X {foo} Y {dni}',
        values: {'dni': ''},
      );
      expect(text, 'X — Y —');
    });

    test('cuerpo vacío usa fallback con nombre', () {
      final text = renderWhatsAppPlantilla(
        '  ',
        values: {'nombre': 'Carlos'},
      );
      expect(text, contains('Carlos'));
      expect(text, contains('App Recaudo Legal'));
    });
  });

  group('buildWhatsAppMessage con cuerpo custom', () {
    test('usa cuerpo y mapa de valores', () {
      final msg = buildWhatsAppMessage(
        clientName: 'X',
        cuerpo: 'Hola {nombre}, deuda {deuda}',
        values: {'nombre': 'Luis', 'deuda': 'S/ 10.00'},
      );
      expect(msg, 'Hola Luis, deuda S/ 10.00');
    });

    test('sin cuerpo usa template por defecto', () {
      expect(
        buildWhatsAppMessage(clientName: 'Rosa'),
        contains('Rosa'),
      );
      expect(
        buildWhatsAppMessage(clientName: 'Rosa'),
        startsWith('Hola Rosa'),
      );
    });
  });
}
