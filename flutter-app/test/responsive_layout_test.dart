import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/utils/responsive.dart';

void main() {
  test('la lista queda más ancha que la ficha en pantallas típicas', () {
    final wide = ResponsiveBreakpoints.masterDetailWidths(total: 1600);
    expect(wide.master, greaterThan(wide.detail));
    expect(wide.master + wide.detail, 1599);

    final laptop = ResponsiveBreakpoints.masterDetailWidths(total: 1280);
    expect(laptop.master, greaterThan(laptop.detail));
    expect(laptop.detail, greaterThanOrEqualTo(340));
  });
}
