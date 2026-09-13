import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/user_model.dart';
import 'package:app_recaudo_legal/utils/section_utils.dart';

UserModel _user({
  required String uid,
  String canal = 'campo',
  List<String> secciones = const [],
  String seccion = '',
  String region = '',
  String zona = '',
}) {
  return UserModel(
    uid: uid,
    nombre: 'Test',
    rol: 'gestor',
    canal: canal,
    secciones: secciones,
    seccion: seccion,
    region: region,
    zona: zona,
  );
}

void main() {
  group('resolveGestorSectionKeys', () {
    test('call gestor with empty secciones uses _CALL_uid', () {
      final keys = resolveGestorSectionKeys(
        _user(uid: 'abc', canal: 'call'),
      );
      expect(keys, ['_CALL_abc']);
    });

    test('call gestor ignores leftover territorial secciones', () {
      final keys = resolveGestorSectionKeys(
        _user(
          uid: 'flor',
          canal: 'call',
          secciones: ['01_1211_A', '01_1211_B'],
          region: '01',
          zona: '1211',
          seccion: 'A',
        ),
      );
      expect(keys, ['_CALL_flor']);
    });

    test('field gestor uses composite secciones', () {
      final keys = resolveGestorSectionKeys(
        _user(
          uid: 'campo1',
          secciones: ['03_3115_H'],
        ),
      );
      expect(keys, ['03_3115_H']);
    });

    test('field gestor builds key from legacy region/zona/seccion', () {
      final keys = resolveGestorSectionKeys(
        _user(
          uid: 'campo2',
          region: '01',
          zona: '1211',
          seccion: 'H',
        ),
      );
      expect(keys, ['01_1211_H']);
    });
  });

  group('primaryDestinationSection', () {
    test('call gestor destination is _CALL_uid', () {
      expect(
        primaryDestinationSection(_user(uid: 'k1', canal: 'call')),
        '_CALL_k1',
      );
    });
  });

  group('callSectionUid', () {
    test('extracts uid from _CALL_ key', () {
      expect(callSectionUid('_CALL_abc123'), 'abc123');
    });

    test('returns null for territorial keys', () {
      expect(callSectionUid('01_1211_H'), isNull);
    });
  });
}
