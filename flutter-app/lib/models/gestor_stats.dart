import 'client_model.dart';

/// Avance agregado por clave de sección Firestore.
class SectionStats {
  final String sectionKey;
  final int total;
  final int visitados;

  const SectionStats({
    required this.sectionKey,
    required this.total,
    required this.visitados,
  });

  int get pendientes => total - visitados;
  double get avancePct => total > 0 ? visitados / total * 100 : 0;
}

/// KPIs calculados a partir de clientes de campaña y ruta del día.
class GestorStats {
  final List<ClientModel> clients;
  final Map<String, int> porEstado;
  final List<SectionStats> porSeccion;
  final int gestionesHoy;
  final int? rutaHoyTotal;
  final int? rutaHoyCompletados;

  const GestorStats({
    required this.clients,
    required this.porEstado,
    required this.porSeccion,
    this.gestionesHoy = 0,
    this.rutaHoyTotal,
    this.rutaHoyCompletados,
  });

  int get total => clients.length;
  int get visitados => clients.where((c) => !c.isPendiente).length;
  int get pendientes => total - visitados;
  double get avancePct => total > 0 ? visitados / total * 100 : 0;

  int get habidos => porEstado['visitado_habido'] ?? 0;
  int get noHabidos => porEstado['visitado_no_habido'] ?? 0;
  int get conGps => clients.where((c) => c.hasCoordinates).length;

  double get deudaTotal =>
      clients.fold(0.0, (s, c) => s + c.importeDeudaAsignada);

  double get deudaGestionada => clients
      .where((c) => !c.isPendiente)
      .fold(0.0, (s, c) => s + c.importeDeudaAsignada);

  double get deudaPendiente =>
      clients.fold(0.0, (s, c) => s + c.importeDeudaPendiente);

  double get recuperadoBanco =>
      clients.fold(0.0, (s, c) => s + c.recuperadoBanco);

  int get promesasCount => clients.where((c) => c.hasPromesa).length;

  double get montoPrometido => clients
      .where((c) => c.hasPromesa)
      .fold(0.0, (s, c) => s + c.montoPromesaPago);

  double? get rutaHoyAvancePct {
    final t = rutaHoyTotal;
    final c = rutaHoyCompletados;
    if (t == null || c == null || t <= 0) return null;
    return c / t * 100;
  }

  /// Construye estadísticas desde la lista de clientes y datos opcionales de ruta.
  factory GestorStats.fromClients(
    List<ClientModel> clients, {
    Map<String, dynamic>? rutaHoy,
  }) {
    final porEstado = <String, int>{};
    for (final c in clients) {
      porEstado[c.estadoGestion] = (porEstado[c.estadoGestion] ?? 0) + 1;
    }

    final sectionKeys = <String>{};
    for (final c in clients) {
      final key = c.seccionKey.isNotEmpty ? c.seccionKey : c.seccion;
      if (key.isNotEmpty) sectionKeys.add(key);
    }

    final porSeccion = sectionKeys.map((key) {
      final sectionClients =
          clients.where((c) => (c.seccionKey.isNotEmpty ? c.seccionKey : c.seccion) == key);
      final total = sectionClients.length;
      final visited = sectionClients.where((c) => !c.isPendiente).length;
      return SectionStats(sectionKey: key, total: total, visitados: visited);
    }).toList()
      ..sort((a, b) => a.sectionKey.compareTo(b.sectionKey));

    final hoy = _todayPrefix();
    final gestionesHoy = clients.where((c) => _isGestionOnDate(c.fechaGestion, hoy)).length;

    int? rutaTotal;
    int? rutaCompletados;
    if (rutaHoy != null) {
      rutaTotal = (rutaHoy['total'] as num?)?.toInt();
      rutaCompletados = (rutaHoy['completados'] as num?)?.toInt();
    }

    return GestorStats(
      clients: clients,
      porEstado: porEstado,
      porSeccion: porSeccion,
      gestionesHoy: gestionesHoy,
      rutaHoyTotal: rutaTotal,
      rutaHoyCompletados: rutaCompletados,
    );
  }

  static String _todayPrefix() {
    final n = DateTime.now();
    final y = n.year.toString().padLeft(4, '0');
    final m = n.month.toString().padLeft(2, '0');
    final d = n.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  static bool _isGestionOnDate(String raw, String datePrefix) {
    if (raw.isEmpty || datePrefix.isEmpty) return false;
    if (raw.startsWith(datePrefix)) return true;
    try {
      final dt = DateTime.parse(raw);
      final y = dt.year.toString().padLeft(4, '0');
      final m = dt.month.toString().padLeft(2, '0');
      final d = dt.day.toString().padLeft(2, '0');
      return '$y-$m-$d' == datePrefix;
    } catch (_) {
      return false;
    }
  }
}
