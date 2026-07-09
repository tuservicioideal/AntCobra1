import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/utils/gestion_monto_rules.dart';

void main() {
  group('GestionMontoRules.requiresMontoPanel', () {
    test('promesa de pago parcial', () {
      expect(
        GestionMontoRules.requiresMontoPanel(
          n2: 'Promesa de pago',
          n3: 'Promesa parcial',
          n4: 'CAM Promesa parcial',
        ),
        isTrue,
      );
    });

    test('cliente cancelo parcial', () {
      expect(
        GestionMontoRules.requiresMontoPanel(
          n2: 'Cliente cancelo',
          n3: 'Cliente cancelo',
          n4: 'CAM Cliente cancelo parcial',
        ),
        isTrue,
      );
    });

    test('pago a cobrador', () {
      expect(
        GestionMontoRules.requiresMontoPanel(
          n2: 'Caso problema / Reclamo',
          n3: 'Pago a socia o gerente',
          n4: 'CAM Pago a cobrador',
        ),
        isTrue,
      );
    });

    test('renuente no activa panel', () {
      expect(
        GestionMontoRules.requiresMontoPanel(
          n2: 'Renuente',
          n3: 'Consultora renuente',
          n4: 'CAM Consultora renuente',
        ),
        isFalse,
      );
    });
  });

  group('GestionMontoRules.showFechaField', () {
    test('promesa de pago muestra fecha', () {
      expect(
        GestionMontoRules.showFechaField(n2: 'Promesa de pago'),
        isTrue,
      );
    });

    test('cliente cancelo no muestra fecha', () {
      expect(
        GestionMontoRules.showFechaField(n2: 'Cliente cancelo'),
        isFalse,
      );
    });
  });

  group('GestionMontoRules labels', () {
    test('monto pagado para cancelo', () {
      expect(
        GestionMontoRules.montoLabel(n2: 'Cliente cancelo'),
        contains('pagado'),
      );
    });
  });
}
