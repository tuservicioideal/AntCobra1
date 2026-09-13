import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/services/caso_service.dart';
import 'package:app_recaudo_legal/utils/caso_problema.dart';
import 'package:app_recaudo_legal/utils/client_status_ui.dart';
import 'package:app_recaudo_legal/utils/user_admin_utils.dart';

void main() {
  group('caso_problema', () {
    test('tipos y etapas conocidos', () {
      expect(isCasoTipo('suplantacion'), isTrue);
      expect(isCasoTipo('no_hizo_pedido'), isTrue);
      expect(isCasoTipo('completo_pedido_socia'), isTrue);
      expect(isCasoTipo('pendiente'), isFalse);
      expect(isEtapaAbierta('nuevo'), isTrue);
      expect(isEtapaCerrada('resuelto'), isTrue);
      expect(isEtapaAbierta('no_procede'), isFalse);
    });

    test('labels', () {
      expect(casoTipoLabel('no_hizo_pedido'), 'No hizo pedido');
      expect(
        casoTipoLabel('completo_pedido_socia'),
        'Completó el pedido la socia',
      );
      expect(casoEtapaLabel('en_gestion'), 'En gestión');
    });

    test('casoTipoFromNivel3 red de seguridad', () {
      expect(casoTipoFromNivel3('No hizo pedido'), 'no_hizo_pedido');
      expect(
        casoTipoFromNivel3('Completo pedido socia o gerente'),
        'completo_pedido_socia',
      );
      expect(casoTipoFromNivel3('Desastre natural'), isNull);
    });

    test('canMoveCasoEtapa', () {
      expect(canMoveCasoEtapa('nuevo', 'en_gestion'), isTrue);
      expect(canMoveCasoEtapa('nuevo', 'nuevo'), isFalse);
      expect(canMoveCasoEtapa('en_gestion', 'resuelto'), isTrue);
    });
  });

  group('CasoService.resolveOpenAction', () {
    test('remark when open exists', () {
      expect(
        CasoService.resolveOpenAction(hasOpen: true, hasClosed: true),
        'remark',
      );
    });
    test('reopen when only closed', () {
      expect(
        CasoService.resolveOpenAction(hasOpen: false, hasClosed: true),
        'reopen',
      );
    });
    test('create when none', () {
      expect(
        CasoService.resolveOpenAction(hasOpen: false, hasClosed: false),
        'create',
      );
    });
  });

  group('normalizeRoleCanal resolutor', () {
    test('acepta resolutor y fuerza canal campo', () {
      final r = normalizeRoleCanal('resolutor', 'call');
      expect(r.rol, 'resolutor');
      expect(r.canal, 'campo');
    });

    test('resolutor no exige territorio', () {
      expect(requiresTerritorialSections('resolutor', 'campo'), isFalse);
      expect(shouldShowTerritorialPicker('resolutor', 'campo'), isFalse);
    });
  });

  group('clientStatusLabel nuevos estados', () {
    test('labels', () {
      expect(clientStatusLabel('no_hizo_pedido'), 'No hizo pedido');
      expect(
        clientStatusLabel('completo_pedido_socia'),
        'Completó el pedido la socia',
      );
    });
  });
}
