import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/widgets/tramo_filter_bar.dart';

ClientModel _client({required String id, int tramo = 1}) {
  return ClientModel(
    id: id,
    nombreCompleto: 'Cliente $id',
    tramoActual: tramo,
    estadoGestion: 'pendiente',
    activoEnCartera: true,
    estadoCiclo: 'activa',
  );
}

void main() {
  testWidgets('tocar E2 notifica la etapa y resalta el chip', (tester) async {
    int? tapped;
    final selected = <int>{};

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              return TramoFilterBar(
                clients: [
                  _client(id: 'a', tramo: 1),
                  _client(id: 'b', tramo: 2),
                  _client(id: 'c', tramo: 3),
                ],
                selected: selected,
                onTap: (tramo) {
                  tapped = tramo;
                  setState(() {
                    if (selected.contains(tramo)) {
                      selected.clear();
                    } else {
                      selected
                        ..clear()
                        ..add(tramo);
                    }
                  });
                },
              );
            },
          ),
        ),
      ),
    );

    expect(find.text('E1 1'), findsOneWidget);
    expect(find.text('E2 1'), findsOneWidget);
    expect(find.text('E3 1'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('tramo-filter-E2')));
    await tester.pump();

    expect(tapped, 2);
    expect(find.text('E2 1'), findsOneWidget);
  });

  testWidgets('TramoBadge muestra E3 para tramo alto', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: TramoBadge(tramo: 4),
        ),
      ),
    );
    expect(find.text('E3'), findsOneWidget);
  });
}
