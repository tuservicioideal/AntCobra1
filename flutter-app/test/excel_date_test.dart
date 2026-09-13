import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/utils/excel_date.dart';

void main() {
  group('parseExcelFecha', () {
    test('parsea dd/MM/yyyy', () {
      expect(parseExcelFecha('15/09/2026'), DateTime(2026, 9, 15));
    });

    test('parsea yyyy-MM-dd', () {
      expect(parseExcelFecha('2026-09-15'), DateTime(2026, 9, 15));
    });

    test('parsea dd-MM-yyyy', () {
      expect(parseExcelFecha('15-09-2026'), DateTime(2026, 9, 15));
    });

    test('parsea yyyy/MM/dd', () {
      expect(parseExcelFecha('2026/09/15'), DateTime(2026, 9, 15));
    });

    test('parsea dd/MM/yy con año corto', () {
      expect(parseExcelFecha('15/09/26'), DateTime(2026, 9, 15));
    });

    test('parsea MM/dd/yyyy cuando el día > 12', () {
      expect(parseExcelFecha('09/15/2026'), DateTime(2026, 9, 15));
    });

    test('prefiere dd/MM cuando ambos ≤ 12', () {
      expect(parseExcelFecha('05/09/2026'), DateTime(2026, 9, 5));
    });

    test('parsea serial Excel', () {
      final expected = DateTime(2026, 9, 15);
      final serial =
          expected.difference(DateTime(1899, 12, 30)).inDays.toString();
      expect(parseExcelFecha(serial), expected);
    });

    test('rechaza vacíos y nullish', () {
      expect(parseExcelFecha(null), isNull);
      expect(parseExcelFecha(''), isNull);
      expect(parseExcelFecha('none'), isNull);
      expect(parseExcelFecha('-'), isNull);
    });

    test('DateTime se normaliza a solo fecha', () {
      expect(
        parseExcelFecha(DateTime(2026, 9, 15, 14, 30)),
        DateTime(2026, 9, 15),
      );
    });
  });

  group('dateOnly', () {
    test('recorta hora', () {
      expect(dateOnly(DateTime(2026, 9, 15, 18, 0)), DateTime(2026, 9, 15));
    });
  });
}
