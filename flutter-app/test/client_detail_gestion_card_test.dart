import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/services/nivel_catalog_service.dart';
import 'package:app_recaudo_legal/widgets/client_detail/client_detail_gestion_card.dart';

void main() {
  late TextEditingController montoController;

  setUp(() {
    montoController = TextEditingController();
  });

  tearDown(() {
    montoController.dispose();
  });

  Future<void> pumpCard(
    WidgetTester tester, {
    required void Function(String estado, String label) onSpecial,
    bool gpsReady = true,
    bool lockCanalToTel = true,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ClientDetailGestionCard(
              catalogLoading: false,
              catalogLoaded: false,
              nivelCatalog: NivelCatalogService(),
              canal: 'TEL',
              nivel1: '',
              nivel2: '',
              nivel3: '',
              nivel4: '',
              fechaPromesa: '',
              montoController: montoController,
              deudaPendiente: 900,
              gpsReady: gpsReady,
              saving: false,
              lockCanalToTel: lockCanalToTel,
              requireGps: false,
              onCanalChanged: (_) {},
              onNivel1Changed: (_) {},
              onNivel2Changed: (_) {},
              onNivel3Changed: (_) {},
              onNivel4Changed: (_) {},
              onPickFechaPromesa: () {},
              onMontoChanged: (_) {},
              onRegister: () {},
              onSpecialStatus: onSpecial,
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('muestra los 4 escenarios del resolutor tras el registro',
      (tester) async {
    await pumpCard(tester, onSpecial: (_, __) {});

    expect(find.text('Gestión telefónica (Call Center)'), findsOneWidget);
    expect(find.text('Casos al resolutor (opcional)'), findsOneWidget);
    expect(find.text('Suplantación'), findsOneWidget);
    expect(find.text('Pago no registrado'), findsOneWidget);
    expect(find.text('No hizo pedido'), findsOneWidget);
    expect(find.text('Completó el pedido la socia'), findsOneWidget);

    final bannerY =
        tester.getTopLeft(find.text('Gestión telefónica (Call Center)')).dy;
    final specialY =
        tester.getTopLeft(find.text('Casos al resolutor (opcional)')).dy;
    final catalogY = tester
        .getTopLeft(find.text(
            'Catálogo de niveles no disponible. Solicite al administrador que lo suba.'))
        .dy;
    expect(bannerY < catalogY, isTrue);
    expect(catalogY < specialY, isTrue);
  });

  testWidgets('No hizo pedido dispara el estado especial', (tester) async {
    String? estado;
    String? label;
    await pumpCard(
      tester,
      onSpecial: (e, l) {
        estado = e;
        label = l;
      },
    );

    await tester.tap(find.text('No hizo pedido'));
    expect(estado, 'no_hizo_pedido');
    expect(label, 'No hizo pedido');
  });

  testWidgets('Completó el pedido la socia dispara el estado especial',
      (tester) async {
    String? estado;
    await pumpCard(
      tester,
      onSpecial: (e, _) => estado = e,
    );

    await tester.tap(find.text('Completó el pedido la socia'));
    expect(estado, 'completo_pedido_socia');
  });
}
