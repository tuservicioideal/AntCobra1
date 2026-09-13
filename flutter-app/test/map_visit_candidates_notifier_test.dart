import 'package:flutter_test/flutter_test.dart';
import 'package:app_recaudo_legal/models/client_model.dart';
import 'package:app_recaudo_legal/models/gestor_stats.dart';
import 'package:app_recaudo_legal/services/map_visit_candidates_notifier.dart';
import 'package:app_recaudo_legal/services/shell_tab_intent_notifier.dart';

ClientModel _client({
  required String id,
  String seccionKey = '01_1211_H',
  double lat = 0,
  double lng = 0,
  String estado = 'pendiente',
}) {
  return ClientModel(
    id: id,
    nombreCompleto: 'Cliente $id',
    seccionKey: seccionKey,
    estadoGestion: estado,
    coordenadaY: lat,
    coordenadaX: lng,
  );
}

void main() {
  group('MapVisitCandidatesNotifier', () {
    test('addAll une por id y acumula secciones distintas', () {
      final notifier = MapVisitCandidatesNotifier();
      notifier.addAll([
        _client(id: 'a', seccionKey: '01_1211_H'),
        _client(id: 'b', seccionKey: '01_1211_H'),
      ]);
      notifier.addAll([
        _client(id: 'b', seccionKey: '01_1211_J'),
        _client(id: 'c', seccionKey: '01_1211_J'),
      ]);

      expect(notifier.count, 3);
      expect(notifier.hasFocus, isTrue);
      expect(notifier.ids, {'a', 'b', 'c'});
    });

    test('addAll vacío no notifica', () {
      final notifier = MapVisitCandidatesNotifier();
      var ticks = 0;
      notifier.addListener(() => ticks++);
      notifier.addAll(const []);
      expect(ticks, 0);
      expect(notifier.hasFocus, isFalse);
    });

    test('remove y clear', () {
      final notifier = MapVisitCandidatesNotifier();
      notifier.addAll([
        _client(id: 'a'),
        _client(id: 'b'),
      ]);
      notifier.remove('a');
      expect(notifier.ids, {'b'});
      notifier.clear();
      expect(notifier.hasFocus, isFalse);
      expect(notifier.count, 0);
    });
  });

  group('ShellTabIntentNotifier', () {
    test('goToMap deja pending y consume lo limpia', () {
      final intent = ShellTabIntentNotifier();
      expect(intent.pending, isNull);
      intent.goToMap();
      expect(intent.pending, HomeShellTab.map);
      intent.consume();
      expect(intent.pending, isNull);
    });
  });

  group('GestorStats.clientsForSection', () {
    test('filtra por seccionKey o seccion legacy', () {
      final stats = GestorStats.fromClients([
        _client(id: '1', seccionKey: '01_1211_H'),
        _client(id: '2', seccionKey: '01_1211_J'),
        ClientModel(id: '3', nombreCompleto: 'Legacy', seccion: '01_1211_H'),
      ]);

      final ofH = stats.clientsForSection('01_1211_H');
      expect(ofH.map((c) => c.id), ['1', '3']);
      expect(stats.porSeccion.length, 2);
    });
  });
}
