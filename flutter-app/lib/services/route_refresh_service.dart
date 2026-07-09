import 'package:flutter/foundation.dart';

/// Notifica a [MyRoutesScreen] que debe recargar tras guardar una ruta en el mapa.
class RouteRefreshService extends ChangeNotifier {
  int _version = 0;

  int get version => _version;

  void notifyRoutesChanged() {
    _version++;
    notifyListeners();
  }
}
