import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/utils/user_admin_utils.dart';

void main() {
  group('normalizeRoleCanal', () {
    test('forces campo for non-gestor roles', () {
      final result = normalizeRoleCanal('admin', 'call');
      expect(result.rol, 'admin');
      expect(result.canal, 'campo');
    });

    test('defaults invalid values', () {
      final result = normalizeRoleCanal('invalid', 'invalid');
      expect(result.rol, 'gestor');
      expect(result.canal, 'campo');
    });
  });

  group('buildSecciones', () {
    test('call gestor with uid assigns _CALL section', () {
      final built = buildSecciones(
        rol: 'gestor',
        canal: 'call',
        uid: 'abc123',
      );
      expect(built.secciones, ['_CALL_abc123']);
    });

    test('call gestor without uid returns empty secciones', () {
      final built = buildSecciones(
        rol: 'gestor',
        canal: 'call',
      );
      expect(built.secciones, isEmpty);
    });

    test('field gestor derives region/zona from composite key', () {
      final built = buildSecciones(
        rol: 'gestor',
        canal: 'campo',
        secciones: ['01_1211_H'],
      );
      expect(built.secciones, ['01_1211_H']);
      expect(built.region, '01');
      expect(built.zona, '1211');
      expect(built.seccion, 'H');
    });

    test('admin has empty secciones', () {
      final built = buildSecciones(
        rol: 'admin',
        canal: 'campo',
      );
      expect(built.secciones, isEmpty);
    });
  });

  group('requiresTerritorialSections', () {
    test('asistente requires sections', () {
      expect(requiresTerritorialSections('asistente', 'campo'), isTrue);
    });

    test('gestor call does not require sections', () {
      expect(requiresTerritorialSections('gestor', 'call'), isFalse);
    });

    test('gestor campo requires sections', () {
      expect(requiresTerritorialSections('gestor', 'campo'), isTrue);
    });

    test('supervisor does not require sections', () {
      expect(requiresTerritorialSections('supervisor', 'campo'), isFalse);
    });
  });

  group('validateUserForm', () {
    test('create requires password', () {
      expect(
        validateUserForm(
          isEdit: false,
          nombre: 'Juan',
          email: 'juan@test.com',
          password: '',
          rol: 'gestor',
          canal: 'campo',
          selectedSecciones: ['01_1211_H'],
        ),
        isNotNull,
      );
    });

    test('gestor call without sections is valid on create', () {
      expect(
        validateUserForm(
          isEdit: false,
          nombre: 'Ana',
          email: 'ana@test.com',
          password: 'secret1',
          rol: 'gestor',
          canal: 'call',
          selectedSecciones: [],
        ),
        isNull,
      );
    });

    test('asistente without sections fails', () {
      expect(
        validateUserForm(
          isEdit: false,
          nombre: 'Ana',
          email: 'ana@test.com',
          password: 'secret1',
          rol: 'asistente',
          canal: 'campo',
          selectedSecciones: [],
        ),
        isNotNull,
      );
    });
  });

  group('shouldShowTerritorialPicker', () {
    test('hidden for call gestor', () {
      expect(shouldShowTerritorialPicker('gestor', 'call'), isFalse);
    });

    test('shown for field gestor', () {
      expect(shouldShowTerritorialPicker('gestor', 'campo'), isTrue);
    });
  });
}
