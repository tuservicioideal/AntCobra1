import 'client_model.dart';
import 'contact_metrics.dart';
import '../utils/campana_banco_utils.dart';

/// Aggregated KPI row for a gestor in the ranking.
class GestorRankingEntry {
  final String uid;
  final String nombre;
  final int gestiones;
  final int habidos;
  final double deudaGestionada;
  final double recuperadoBanco;
  final int promesasCount;
  final double montoPrometido;

  const GestorRankingEntry({
    required this.uid,
    required this.nombre,
    this.gestiones = 0,
    this.habidos = 0,
    this.deudaGestionada = 0,
    this.recuperadoBanco = 0,
    this.promesasCount = 0,
    this.montoPrometido = 0,
  });
}

/// Per-section summary for territory tab.
class SectionStatsEntry {
  final String seccion;
  final int total;
  final int visitados;
  final int pendientes;
  final double deuda;
  final double deudaGestionada;
  final double recuperadoBanco;
  final int geolocated;

  const SectionStatsEntry({
    required this.seccion,
    this.total = 0,
    this.visitados = 0,
    this.pendientes = 0,
    this.deuda = 0,
    this.deudaGestionada = 0,
    this.recuperadoBanco = 0,
    this.geolocated = 0,
  });

  double get avancePct => total > 0 ? visitados / total * 100 : 0;
}

/// Label + value for charts.
class StatsBarItem {
  final String label;
  final double value;
  final int count;

  const StatsBarItem({
    required this.label,
    this.value = 0,
    this.count = 0,
  });
}

/// Full campaign statistics snapshot for the stats UI.
class CampaignStats {
  final List<ClientModel> clients;
  final Map<String, int> statusCounts;
  final Map<int, int> tramoCounts;

  final int total;
  final int gestionados;
  final double avancePct;

  final double deudaAsignada;
  final double deudaPendiente;
  final double recuperadoBanco;
  final double tasaRecuperacionBanco;
  final double deudaGestionada;

  final int promesasCount;
  final double montoPrometido;

  final double porcentajeComisionJefe;
  final double gananciaJefe;

  final int diasTranscurridos;
  final int diasRestantes;
  final double ritmoDiarioRecuperacion;
  final double proyeccionLineal;
  final double proyeccionPromesas;

  final int geolocated;
  final double gpsPct;

  final List<GestorRankingEntry> gestorRanking;
  final List<SectionStatsEntry> sectionStats;
  final List<StatsBarItem> topDepartmentsByCount;
  final List<StatsBarItem> topDepartmentsByDeuda;
  final List<StatsBarItem> topDistrictsByDeuda;

  final List<({String label, int value, int colorValue})> funnelStages;

  final ContactMetrics? contactMetrics;
  final List<CampanaBancoBreakdownEntry> campanaBancoBreakdown;

  const CampaignStats({
    required this.clients,
    this.statusCounts = const {},
    this.tramoCounts = const {},
    this.total = 0,
    this.gestionados = 0,
    this.avancePct = 0,
    this.deudaAsignada = 0,
    this.deudaPendiente = 0,
    this.recuperadoBanco = 0,
    this.tasaRecuperacionBanco = 0,
    this.deudaGestionada = 0,
    this.promesasCount = 0,
    this.montoPrometido = 0,
    this.porcentajeComisionJefe = 15,
    this.gananciaJefe = 0,
    this.diasTranscurridos = 1,
    this.diasRestantes = 0,
    this.ritmoDiarioRecuperacion = 0,
    this.proyeccionLineal = 0,
    this.proyeccionPromesas = 0,
    this.geolocated = 0,
    this.gpsPct = 0,
    this.gestorRanking = const [],
    this.sectionStats = const [],
    this.topDepartmentsByCount = const [],
    this.topDepartmentsByDeuda = const [],
    this.topDistrictsByDeuda = const [],
    this.funnelStages = const [],
    this.contactMetrics,
    this.campanaBancoBreakdown = const [],
  });

  static const statusOrder = [
    'pendiente',
    'visitado_habido',
    'visitado_no_habido',
    'fallecido_inubicable',
    'suplantacion',
    'pago_no_registrado',
  ];

  static const statusLabels = {
    'pendiente': 'Pendiente',
    'visitado_habido': 'Visitado Habido',
    'visitado_no_habido': 'No Habido',
    'fallecido_inubicable': 'Inubicable',
    'suplantacion': 'Suplantación',
    'pago_no_registrado': 'Pago No Reg.',
  };
}
