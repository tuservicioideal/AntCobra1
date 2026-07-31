import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/widgets/multi_territorial_section_picker.dart';

void main() {
  testWidgets(
    'MultiTerritorialSectionPicker does not freeze when parent stores callback list',
    (tester) async {
      var callbackCount = 0;
      var selected = <String>[];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) {
                return MultiTerritorialSectionPicker(
                  catalog: const {},
                  availableSectionKeys: const [],
                  initialSecciones: selected,
                  onSeccionesChanged: (keys) {
                    callbackCount++;
                    setState(() => selected = keys);
                  },
                );
              },
            ),
          ),
        ),
      );

      // Former bug: post-frame notify + list identity compare caused infinite
      // setState. If that returns, pumpAndSettle would hang forever.
      await tester.pumpAndSettle(const Duration(seconds: 2));

      expect(callbackCount, lessThan(3));
      expect(find.text('Secciones asignadas'), findsOneWidget);
      expect(find.text('Ninguna sección seleccionada'), findsOneWidget);
    },
  );
}
