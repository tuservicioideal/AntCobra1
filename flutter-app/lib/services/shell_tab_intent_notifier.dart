import 'package:flutter/foundation.dart';

/// Destinos de tab del [HomeShell] que otras pantallas pueden pedir sin
/// conocer índices numéricos.
enum HomeShellTab { map }

/// Intención de cambio de tab (consumida por [HomeShell]).
class ShellTabIntentNotifier extends ChangeNotifier {
  HomeShellTab? _pending;

  HomeShellTab? get pending => _pending;

  void goToMap() {
    _pending = HomeShellTab.map;
    notifyListeners();
  }

  void consume() {
    if (_pending == null) return;
    _pending = null;
  }
}
