import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/utils/section_load_utils.dart';

void main() {
  group('resolveLoadableSectionIds', () {
    test('usa solo gestores con clientes cuando hay conteos', () {
      final ids = resolveLoadableSectionIds(
        campaignSecciones: ['01_1211_H', '01_1211_Z', 'legacy_empty'],
        hints: const [
          GestorSectionHint(id: '01_1211_H', numClientes: 120),
          GestorSectionHint(id: '01_1211_Z', numClientes: 0),
          GestorSectionHint(id: 'legacy_empty', numClientes: 0),
          GestorSectionHint(id: '_CALL_abc', numClientes: 40),
        ],
      );
      expect(ids, ['01_1211_H', '_CALL_abc']);
    });

    test('si nadie tiene conteo, usa metadata de campaña', () {
      final ids = resolveLoadableSectionIds(
        campaignSecciones: ['01_1211_H', '', '01_1211_J'],
        hints: const [
          GestorSectionHint(id: '01_1211_H'),
          GestorSectionHint(id: 'ghost'),
        ],
      );
      expect(ids, ['01_1211_H', '01_1211_J']);
    });

    test('si no hay metadata ni conteos, lista todos los ids', () {
      final ids = resolveLoadableSectionIds(
        campaignSecciones: null,
        hints: const [
          GestorSectionHint(id: 'b'),
          GestorSectionHint(id: 'a'),
        ],
      );
      expect(ids, ['a', 'b']);
    });
  });

  group('mapPool', () {
    test('no supera la concurrencia máxima', () async {
      var inFlight = 0;
      var maxInFlight = 0;
      final seen = <int>[];

      await mapPool<int, int>(
        List.generate(8, (i) => i),
        (i) async {
          inFlight++;
          if (inFlight > maxInFlight) maxInFlight = inFlight;
          await Future<void>.delayed(const Duration(milliseconds: 15));
          seen.add(i);
          inFlight--;
          return i;
        },
        concurrency: 2,
      );

      expect(maxInFlight, lessThanOrEqualTo(2));
      expect(seen.toSet(), {0, 1, 2, 3, 4, 5, 6, 7});
    });
  });
}
