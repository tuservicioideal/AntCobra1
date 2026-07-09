import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/utils/contact_metrics_utils.dart';

ClientModel _client({
  String estadoGestion = 'pendiente',
  String nivel1 = '',
  String nivel4 = '',
  String canalGestion = '',
  bool hasPromesa = false,
}) {
  return ClientModel(
    id: '1',
    nombreCompleto: 'Test Cliente',
    estadoGestion: estadoGestion,
    nivel1: nivel1,
    nivel4: nivel4,
    canalGestion: canalGestion,
    montoPromesaPago: hasPromesa ? 100 : 0,
    activoEnCartera: true,
    estadoCiclo: 'activa',
  );
}

void main() {
  group('computeContactMetrics', () {
    test('cuenta pendientes y gestionados', () {
      final m = computeContactMetrics([
        _client(),
        _client(estadoGestion: 'visitado_habido', nivel1: 'Contacto efectivo'),
      ]);
      expect(m.total, 2);
      expect(m.pendientes, 1);
      expect(m.totalGestionados, 1);
      expect(m.contactoEfectivo, 1);
    });

    test('detecta SMS y WSP enviados', () {
      final m = computeContactMetrics([
        _client(
          estadoGestion: 'visitado_no_habido',
          canalGestion: 'TEL',
          nivel4: 'TEL Envio de SMS',
          nivel1: 'Contacto no efectivo',
        ),
        _client(
          estadoGestion: 'visitado_no_habido',
          canalGestion: 'TEL',
          nivel4: 'TEL Envio de WSP',
          nivel1: 'Contacto no efectivo',
        ),
      ]);
      expect(m.smsEnviados, 1);
      expect(m.wspEnviados, 1);
      expect(m.virtualEnviados, 2);
    });

    test('contacto efectivo TEL incrementa pct respuesta', () {
      final m = computeContactMetrics([
        _client(
          estadoGestion: 'visitado_habido',
          canalGestion: 'TEL',
          nivel1: 'Contacto efectivo',
          nivel4: 'TEL Promesa total',
        ),
        _client(
          estadoGestion: 'visitado_no_habido',
          canalGestion: 'TEL',
          nivel4: 'TEL Mensaje en grabadora',
          nivel1: 'No contacto',
        ),
      ]);
      expect(m.canalTel, 2);
      expect(m.contactoEfectivoTel, 1);
      expect(m.pctRespuestaTel, 50);
      expect(m.llamadaSinRespuesta, 1);
    });

    test('canal CAM vs TEL', () {
      final m = computeContactMetrics([
        _client(
          estadoGestion: 'visitado_habido',
          canalGestion: 'CAM',
          nivel1: 'Contacto efectivo',
        ),
        _client(
          estadoGestion: 'visitado_habido',
          canalGestion: 'TEL',
          nivel1: 'Contacto efectivo',
        ),
      ]);
      expect(m.canalCam, 1);
      expect(m.canalTel, 1);
      expect(m.pctCanalCam, 50);
      expect(m.pctCanalTel, 50);
    });
  });

  group('clientMatchesSearchQuery', () {
    test('requiere al menos 2 caracteres', () {
      final c = _client();
      expect(clientMatchesSearchQuery(c, 'T'), isFalse);
      expect(clientMatchesSearchQuery(c, 'Te'), isTrue);
    });

    test('busca por DNI y código', () {
      final c = ClientModel(
        id: '1',
        nombreCompleto: 'Ana',
        numeroDocumento: '12345678',
        codigoCliente: 'CLI-99',
        activoEnCartera: true,
        estadoCiclo: 'activa',
      );
      expect(clientMatchesSearchQuery(c, '1234'), isTrue);
      expect(clientMatchesSearchQuery(c, 'cli-9'), isTrue);
    });
  });
}
