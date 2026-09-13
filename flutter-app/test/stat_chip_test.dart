import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/widgets/stat_card.dart';

void main() {
  testWidgets('StatChip llama onTap y refleja selección', (tester) async {
    var taps = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatChip(
            label: 'Pendientes',
            value: '412',
            icon: Icons.pending_outlined,
            color: Colors.orange,
            selected: true,
            onTap: () => taps++,
          ),
        ),
      ),
    );

    expect(find.text('412'), findsOneWidget);
    expect(find.text('Pendientes'), findsOneWidget);
    await tester.tap(find.text('Pendientes'));
    expect(taps, 1);
  });
}
