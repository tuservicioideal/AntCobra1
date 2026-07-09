import '../models/client_model.dart';

/// Clave interna para clientes sin número de campaña del banco.
const String kSinCampanaBancoKey = '_sin_campana_';

/// Etiqueta visible para [kSinCampanaBancoKey].
const String kSinCampanaBancoLabel = 'Sin campaña';

/// Valores distintos de campaña del banco entre clientes activos.
List<String> distinctCampanaBancoValues(List<ClientModel> clients) {
  final values = <String>{};
  var hasEmpty = false;
  for (final c in clients) {
    if (!c.isActiveForGestor) continue;
    final v = c.campanaBanco.trim();
    if (v.isEmpty) {
      hasEmpty = true;
    } else {
      values.add(v);
    }
  }
  final sorted = values.toList()..sort();
  if (hasEmpty) sorted.add(kSinCampanaBancoKey);
  return sorted;
}

bool matchesCampanaBanco(ClientModel client, String? filter) {
  if (filter == null) return true;
  final value = client.campanaBanco.trim();
  if (filter == kSinCampanaBancoKey) return value.isEmpty;
  return value == filter;
}

List<ClientModel> applyCampanaBancoFilter(
  List<ClientModel> clients,
  String? filter,
) {
  if (filter == null) return clients;
  return clients.where((c) => matchesCampanaBanco(c, filter)).toList();
}

String campanaBancoFilterLabel(String? filter) {
  if (filter == null) return 'Todas las campañas';
  if (filter == kSinCampanaBancoKey) return kSinCampanaBancoLabel;
  return filter;
}

bool campanaBancoFilterBarVisible(List<String> available) {
  if (available.isEmpty) return false;
  if (available.length == 1 && available.first != kSinCampanaBancoKey) {
    return false;
  }
  return available.length > 1 ||
      (available.length == 1 && available.first == kSinCampanaBancoKey);
}

/// Per [campana_banco] summary for executive dashboard cards.
class CampanaBancoBreakdownEntry {
  final String key;
  final String label;
  final int cuentas;
  final double deudaAsignada;
  final double recuperado;
  final double pctRecuperacion;
  final int tramoPromedio;

  const CampanaBancoBreakdownEntry({
    required this.key,
    required this.label,
    this.cuentas = 0,
    this.deudaAsignada = 0,
    this.recuperado = 0,
    this.pctRecuperacion = 0,
    this.tramoPromedio = 0,
  });
}

List<CampanaBancoBreakdownEntry> buildCampanaBancoBreakdown(
  List<ClientModel> clients,
) {
  final buckets = <String, List<ClientModel>>{};

  for (final c in clients) {
    if (!c.isActiveForGestor) continue;
    final key = c.campanaBanco.trim().isEmpty
        ? kSinCampanaBancoKey
        : c.campanaBanco.trim();
    buckets.putIfAbsent(key, () => []).add(c);
  }

  final entries = <CampanaBancoBreakdownEntry>[];
  for (final entry in buckets.entries) {
    final list = entry.value;
    final asignada =
        list.fold(0.0, (s, c) => s + c.importeDeudaAsignada);
    final recuperado = list.fold(0.0, (s, c) => s + c.recuperadoBanco);
    final tramoSum = list.fold(0, (s, c) => s + c.tramoActual);
    entries.add(CampanaBancoBreakdownEntry(
      key: entry.key,
      label: campanaBancoFilterLabel(entry.key),
      cuentas: list.length,
      deudaAsignada: asignada,
      recuperado: recuperado,
      pctRecuperacion: asignada > 0 ? recuperado / asignada * 100 : 0,
      tramoPromedio: list.isNotEmpty ? (tramoSum / list.length).round() : 0,
    ));
  }

  entries.sort((a, b) => a.label.compareTo(b.label));
  return entries;
}
