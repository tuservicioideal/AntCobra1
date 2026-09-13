/// Cómo elegir qué secciones de gestores leer y con cuánta paralelismo.
class GestorSectionHint {
  final String id;
  final int? numClientes;

  const GestorSectionHint({required this.id, this.numClientes});
}

/// Evita barrer cientos de carpetas vacías (legado) al armar el panel admin.
///
/// 1. Si hay `num_clientes > 0` en documentos gestor, solo esas.
/// 2. Si no, la lista `secciones` del doc de campaña.
/// 3. Si no, todos los ids (comportamiento anterior).
List<String> resolveLoadableSectionIds({
  List<dynamic>? campaignSecciones,
  required List<GestorSectionHint> hints,
}) {
  final withClients = hints
      .where((h) => (h.numClientes ?? 0) > 0)
      .map((h) => h.id)
      .where((id) => id.isNotEmpty)
      .toList()
    ..sort();
  if (withClients.isNotEmpty) return withClients;

  final fromMeta = <String>[];
  if (campaignSecciones != null) {
    for (final raw in campaignSecciones) {
      final s = raw.toString().trim();
      if (s.isNotEmpty) fromMeta.add(s);
    }
    fromMeta.sort();
    if (fromMeta.isNotEmpty) return fromMeta;
  }

  final all = hints.map((h) => h.id).where((id) => id.isNotEmpty).toList()
    ..sort();
  return all;
}

int defaultSectionLoadConcurrency({required bool isWeb}) => isWeb ? 4 : 8;

/// Ejecuta [mapper] sobre [items] con un tope de tareas en vuelo.
Future<List<T>> mapPool<T, E>(
  Iterable<E> items,
  Future<T> Function(E item) mapper, {
  int concurrency = 4,
}) async {
  final list = items.toList();
  if (list.isEmpty) return <T>[];
  final n = concurrency.clamp(1, list.length);
  final results = List<T?>.filled(list.length, null);
  var next = 0;

  Future<void> worker() async {
    while (true) {
      final i = next;
      next++;
      if (i >= list.length) return;
      results[i] = await mapper(list[i]);
    }
  }

  await Future.wait(List.generate(n, (_) => worker()));
  return results.cast<T>();
}
