import '../models/client_model.dart';
import 'contact_metrics_utils.dart';

/// Default page size for client lists in the gestor app.
const int kClientListPageSize = 30;

/// In-memory pagination helper for client lists.
class ClientListPagination {
  ClientListPagination({this.pageSize = kClientListPageSize});

  final int pageSize;
  int page = 0;
  int totalItems = 0;

  int get totalPages =>
      totalItems == 0 ? 1 : ((totalItems - 1) ~/ pageSize) + 1;

  int get startIndex => page * pageSize;

  int get endIndex {
    final end = startIndex + pageSize;
    return end > totalItems ? totalItems : end;
  }

  bool get hasPrevious => page > 0;

  bool get hasNext => page < totalPages - 1;

  bool get needsBar => totalItems > pageSize;

  void syncTotal(int count) {
    totalItems = count;
    if (page >= totalPages) {
      page = totalPages > 0 ? totalPages - 1 : 0;
    }
  }

  void reset() {
    page = 0;
  }

  void next() {
    if (hasNext) page++;
  }

  void previous() {
    if (hasPrevious) page--;
  }

  void goTo(int newPage) {
    if (newPage < 0) {
      page = 0;
    } else if (newPage >= totalPages) {
      page = totalPages > 0 ? totalPages - 1 : 0;
    } else {
      page = newPage;
    }
  }

  List<T> slice<T>(List<T> list) {
    syncTotal(list.length);
    if (list.isEmpty) return const [];
    final start = startIndex;
    final end = endIndex;
    if (start >= list.length) return const [];
    return list.sublist(start, end > list.length ? list.length : end);
  }
}

/// Unified client search for dashboard-style lists.
bool matchesClientSearch(ClientModel c, String query) {
  if (query.trim().isEmpty) return true;
  final q = query.toLowerCase().trim();
  return c.displayName.toLowerCase().contains(q) ||
      c.nombreCompleto.toLowerCase().contains(q) ||
      c.numeroDocumento.toLowerCase().contains(q) ||
      c.codigoCliente.toLowerCase().contains(q) ||
      c.direccion.toLowerCase().contains(q) ||
      c.telefonoMovil.toLowerCase().contains(q) ||
      clientMatchesSearchQuery(c, query);
}

/// Search for lightweight route client maps (Mis rutas).
bool matchesRouteClientMap(Map<String, dynamic> c, String query) {
  if (query.trim().isEmpty) return true;
  final q = query.toLowerCase().trim();
  final nombre = c['nombre']?.toString().toLowerCase() ?? '';
  final codigo = c['codigo_cliente']?.toString().toLowerCase() ?? '';
  final dni = c['numero_documento']?.toString().toLowerCase() ??
      c['dni']?.toString().toLowerCase() ??
      '';
  return nombre.contains(q) || codigo.contains(q) || dni.contains(q);
}
