import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/utils/territorial_utils.dart';

void main() {
  group('groupSeccionesByHierarchy', () {
    test('groups by region and zona', () {
      final grouped = groupSeccionesByHierarchy([
        '01_1211_H',
        '01_1211_C',
        '01_1300_A',
        '02_2000_B',
        '_CALL_abc',
        'invalid',
      ]);

      expect(grouped.keys.toList(), ['01', '02']);
      expect(grouped['01']!.keys.toList()..sort(), ['1211', '1300']);
      expect(grouped['01']!['1211'], ['01_1211_C', '01_1211_H']);
      expect(grouped['02']!['2000'], ['02_2000_B']);
    });

    test('dedupes keys', () {
      final grouped = groupSeccionesByHierarchy([
        '01_1211_H',
        '01_1211_H',
      ]);
      expect(grouped['01']!['1211'], ['01_1211_H']);
    });
  });

  group('remove helpers', () {
    final keys = ['01_1211_H', '01_1211_C', '01_1300_A', '02_2000_B'];

    test('removeRegion drops all keys of that region', () {
      expect(removeRegion(keys, '01'), ['02_2000_B']);
      expect(countSeccionesInRegion(keys, '01'), 3);
    });

    test('removeZona drops only that zona', () {
      expect(removeZona(keys, '01', '1211'), ['01_1300_A', '02_2000_B']);
      expect(countSeccionesInZona(keys, '01', '1211'), 2);
    });

    test('removeSeccion drops one key', () {
      expect(removeSeccion(keys, '01_1211_H'), [
        '01_1211_C',
        '01_1300_A',
        '02_2000_B',
      ]);
    });

    test('removeRegion preserves non-composite keys', () {
      expect(removeRegion(['01_1211_H', '_CALL_x'], '01'), ['_CALL_x']);
    });
  });

  group('legacyFieldsFromSecciones', () {
    test('uses first composite key', () {
      final legacy = legacyFieldsFromSecciones(['01_1211_H', '02_2000_B']);
      expect(legacy.region, '01');
      expect(legacy.zona, '1211');
      expect(legacy.seccionLetter, 'H');
    });

    test('empty when no composite keys', () {
      final legacy = legacyFieldsFromSecciones(['_CALL_x']);
      expect(legacy.region, '');
      expect(legacy.zona, '');
      expect(legacy.seccionLetter, '');
    });
  });
}
