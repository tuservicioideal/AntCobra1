import 'package:flutter/foundation.dart';

import '../models/client_model.dart';
import '../utils/campana_banco_utils.dart';

/// Estado compartido del filtro por **Nº campaña banco** (columna E del Excel).
///
/// El filtro persiste entre pestañas (Dashboard, Mapa, Perfil, Stats) vía
/// [ChangeNotifierProvider] en [main.dart]. Se limpia al cerrar sesión.
class CampanaBancoFilterNotifier extends ChangeNotifier {
  String? _selected;
  List<String> _available = const [];

  String? get selected => _selected;
  List<String> get available => List.unmodifiable(_available);

  bool get hasActiveFilter => _selected != null;

  bool get showFilterBar => campanaBancoFilterBarVisible(_available);

  /// Recalcula chips disponibles desde clientes activos del gestor.
  /// Si la campaña seleccionada ya no existe, la limpia automáticamente.
  void updateAvailable(List<ClientModel> clients) {
    try {
      final next = distinctCampanaBancoValues(clients);
      final prevSelected = _selected;
      final selectionCleared =
          prevSelected != null && !next.contains(prevSelected);

      if (selectionCleared) {
        _selected = null;
      }

      if (!listEquals(_available, next) || selectionCleared) {
        _available = next;
        notifyListeners();
      }
    } catch (e, st) {
      debugPrint('CampanaBancoFilterNotifier.updateAvailable: $e\n$st');
    }
  }

  /// Selecciona una campaña banco concreta o `null` para ver todas.
  void select(String? campana) {
    if (_selected == campana) return;
    _selected = campana;
    notifyListeners();
  }

  /// Quita el filtro activo pero conserva las opciones disponibles.
  void reset() {
    if (_selected == null) return;
    _selected = null;
    notifyListeners();
  }

  /// Limpia selección y opciones (p. ej. al cerrar sesión).
  void clearAll() {
    if (_selected == null && _available.isEmpty) return;
    _selected = null;
    _available = const [];
    notifyListeners();
  }
}
