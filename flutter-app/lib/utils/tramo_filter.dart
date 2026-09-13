import '../models/client_model.dart';

/// Etapas de ciclo que el gestor puede filtrar (E1 / E2 / E3).
const tramoFilterOptions = [1, 2, 3];

/// Tramo efectivo del cliente (0 o negativo → etapa 1; 3 o más → etapa 3).
/// Alineado con [ClientModel.cicloLabel] y con las etiquetas E1/E2/E3.
int effectiveTramo(ClientModel client) {
  final t = client.tramoActual;
  if (t <= 0) return 1;
  if (t >= 3) return 3;
  return t;
}

/// Etiqueta corta de etapa: E1 / E2 / E3.
String tramoLabel(int tramo) {
  final t = tramo <= 0 ? 1 : (tramo >= 3 ? 3 : tramo);
  return 'E$t';
}

/// Clave estable para invalidar caches de filtrado.
String tramoFilterCacheKey(Set<int> selected) {
  if (selected.isEmpty) return '';
  final sorted = selected.toList()..sort();
  return sorted.join(',');
}

bool matchesTramoFilter(ClientModel client, Set<int> selected) {
  if (selected.isEmpty) return true;
  return selected.contains(effectiveTramo(client));
}

List<ClientModel> applyTramoFilter(
  List<ClientModel> clients,
  Set<int> selected,
) {
  if (selected.isEmpty) return clients;
  return clients.where((c) => matchesTramoFilter(c, selected)).toList();
}

/// Conteo por etapa efectiva (1, 2, 3) sobre la lista dada.
Map<int, int> countByTramo(Iterable<ClientModel> clients) {
  final counts = {1: 0, 2: 0, 3: 0};
  for (final c in clients) {
    final t = effectiveTramo(c);
    counts[t] = (counts[t] ?? 0) + 1;
  }
  return counts;
}

/// Un toque selecciona esa etapa; el mismo toque la quita (vuelve a “todas”).
Set<int> toggleExclusiveTramo(Set<int> selected, int tramo) {
  if (selected.length == 1 && selected.contains(tramo)) {
    return <int>{};
  }
  return {tramo};
}
