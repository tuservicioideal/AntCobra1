import 'package:app_recaudo_legal/models/whatsapp_plantilla.dart';
import 'package:app_recaudo_legal/utils/whatsapp_plantilla_renderer.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('lista de plantillas muestra nombre y preview', (tester) async {
    final plantillas = [
      const WhatsAppPlantilla(
        id: '1',
        nombre: 'Primer contacto',
        cuerpo: 'Hola {nombre}, debe {deuda}',
        origen: 'personal',
        predeterminada: true,
      ),
      const WhatsAppPlantilla(
        id: '2',
        nombre: 'Recordatorio',
        cuerpo: 'Buen día {nombre}',
        origen: 'empresa',
      ),
    ];
    final values = sampleWhatsAppPlaceholders();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: plantillas.map((p) {
              final preview = renderWhatsAppPlantilla(p.cuerpo, values: values);
              return ListTile(
                title: Text(p.nombre),
                subtitle: Text(preview),
              );
            }).toList(),
          ),
        ),
      ),
    );

    expect(find.text('Primer contacto'), findsOneWidget);
    expect(find.text('Recordatorio'), findsOneWidget);
    expect(find.textContaining('Juan Pérez'), findsWidgets);
    expect(find.textContaining('S/ 1.234,56'), findsOneWidget);
  });

  test('chip variables insertan en texto', () {
    const base = 'Hola ';
    const tag = '{nombre}';
    final next = '$base$tag';
    expect(next, 'Hola {nombre}');
    expect(
      renderWhatsAppPlantilla(next, values: {'nombre': 'Ana'}),
      'Hola Ana',
    );
  });
}
