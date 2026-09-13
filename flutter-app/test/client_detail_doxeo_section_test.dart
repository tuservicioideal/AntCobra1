import 'package:app_recaudo_legal/services/doxeo_queue_service.dart';
import 'package:app_recaudo_legal/widgets/client_detail/client_detail_doxeo_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('muestra el resultado guardado de cada tipo de consulta',
      (tester) async {
    final consultas = [
      DoxeoJob(
        id: 'j1',
        comandoId: 'reniec',
        comandoNombre: 'RENIEC',
        estado: 'completado',
        dni: '12345678',
        creadoAt: DateTime(2026, 9, 10, 18, 5),
        parsed: const {'nombre': 'PEREZ LOPEZ', 'phones': ['999111222']},
        hasData: true,
      ),
      DoxeoJob(
        id: 'j2',
        comandoId: '',
        comandoNombre: 'Solo DNI',
        estado: 'completado',
        dni: '12345678',
        creadoAt: DateTime(2026, 9, 9, 11, 0),
        parsed: const {'nombre': 'PEREZ DNI'},
        hasData: true,
      ),
    ];

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: DoxeoConsultasGuardadas(consultas: consultas),
          ),
        ),
      ),
    );

    expect(find.text('Consultas guardadas'), findsOneWidget);
    expect(find.text('RENIEC'), findsOneWidget);
    expect(find.text('Solo DNI'), findsOneWidget);
    expect(find.text('PEREZ LOPEZ'), findsOneWidget);
    expect(find.text('PEREZ DNI'), findsOneWidget);
  });

  testWidgets('muestra PDF aunque no haya datos OSINT parseados', (tester) async {
    final job = DoxeoJob(
      id: 'j-pdf',
      comandoNombre: 'OSINT',
      estado: 'completado',
      dni: '12345678',
      hasData: false,
      archivos: const [
        DoxeoArchivo(
          path: 'doxeo_jobs/j-pdf/doc_0.pdf',
          fileName: 'ficha.pdf',
          mimeType: 'application/pdf',
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DoxeoJobView(job: job),
        ),
      ),
    );

    expect(
      find.text('El bot respondió pero sin datos útiles para este DNI.'),
      findsNothing,
    );
    expect(find.text('Documentos'), findsOneWidget);
    expect(find.text('ficha.pdf'), findsOneWidget);
  });
}
