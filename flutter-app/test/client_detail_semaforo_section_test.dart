import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/models/semaforo.dart';
import 'package:app_recaudo_legal/widgets/client_detail/client_detail_semaforo_section.dart';

void main() {
  group('SemaforoNivel', () {
    test('normalize acepta ids válidos y rechaza basura', () {
      expect(normalizeSemaforo('rojo'), 'rojo');
      expect(normalizeSemaforo('VERDE'), 'verde');
      expect(normalizeSemaforo(''), '');
      expect(normalizeSemaforo('azul'), '');
    });

    test('label y color por id', () {
      expect(labelSemaforo('rojo'), 'Renuente');
      expect(labelSemaforo(null), 'Sin clasificar');
      expect(colorSemaforo('verde'), const Color(0xFF16A34A));
    });
  });

  group('ClientModel.semaforo', () {
    test('fromMap y copyWith', () {
      final c = ClientModel.fromMap('1', {
        'nombre_completo': 'Test',
        'semaforo': 'Amarillo',
      });
      expect(c.semaforo, 'amarillo');
      expect(c.copyWith(semaforo: 'verde').semaforo, 'verde');
      expect(c.copyWith(semaforo: '').semaforo, '');
    });
  });

  testWidgets('ClientDetailSemaforoSection dispara onSave', (tester) async {
    String? saved;
    final client = ClientModel(id: '1', nombreCompleto: 'Ana', semaforo: '');

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClientDetailSemaforoSection(
            client: client,
            onSave: (v) => saved = v,
          ),
        ),
      ),
    );

    expect(find.text('Semáforo'), findsOneWidget);
    expect(find.text('Sin clasificar'), findsOneWidget);

    // Primer círculo = rojo
    final inkWells = find.byType(InkWell);
    expect(inkWells, findsWidgets);
    await tester.tap(inkWells.first);
    await tester.pump();
    expect(saved, 'rojo');
  });
}
