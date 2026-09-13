import 'package:flutter/foundation.dart';

import '../models/client_model.dart';

/// Candidatos enviados desde Perfil hacia el tab Mapa (sesión, no persistidos).
///
/// No forman parte de la ruta hasta que el gestor los marca uno a uno en Mapa.
class MapVisitCandidatesNotifier extends ChangeNotifier {
  final Map<String, ClientModel> _byId = <String, ClientModel>{};

  List<ClientModel> get candidates => List<ClientModel>.unmodifiable(_byId.values);

  Set<String> get ids => Set<String>.unmodifiable(_byId.keys);

  bool get hasFocus => _byId.isNotEmpty;

  int get count => _byId.length;

  bool contains(String id) => _byId.containsKey(id);

  ClientModel? operator [](String id) => _byId[id];

  /// Une por [ClientModel.id]; una segunda tanda desde otra sección se acumula.
  void addAll(Iterable<ClientModel> clients) {
    var changed = false;
    for (final client in clients) {
      final previous = _byId[client.id];
      if (previous == null || previous != client) {
        _byId[client.id] = client;
        changed = true;
      }
    }
    if (changed) notifyListeners();
  }

  void remove(String id) {
    if (_byId.remove(id) == null) return;
    notifyListeners();
  }

  void clear() {
    if (_byId.isEmpty) return;
    _byId.clear();
    notifyListeners();
  }
}
