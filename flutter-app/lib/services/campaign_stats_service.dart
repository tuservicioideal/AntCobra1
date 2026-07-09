import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';

import '../models/campaign_config_model.dart';
import '../models/campaign_stats.dart';
import '../models/client_model.dart';
import '../models/user_model.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/contact_metrics_utils.dart';
import 'campaign_service.dart';
import 'firestore_service.dart';

/// Loads and aggregates campaign-wide statistics for executive dashboards.
class CampaignStatsService {
  final _firestore = FirestoreService();
  final _campaign = CampaignService();
  final _db = FirebaseFirestore.instance;

  CampaignStats? _cache;
  String? _cacheCampaignId;
  String? _cacheSectionsKey;
  String? _cacheCampanaBancoFilter;

  /// Clientes activos sin filtro de campaña del banco (para chips de filtro).
  Future<List<ClientModel>> loadActiveClients({
    required String campaignId,
    List<String>? sectionFilter,
  }) async {
    final sections = sectionFilter ??
        await _campaign.getAvailableSections(campaignId);
    return _loadClientsDeduped(campaignId, sections);
  }

  Future<CampaignStats> loadForCampaign({
    required String campaignId,
    List<String>? sectionFilter,
    String? campanaBancoFilter,
    bool forceRefresh = false,
  }) async {
    final sectionsKey = (sectionFilter ?? []).join('|');
    final campanaKey = campanaBancoFilter ?? '';
    if (!forceRefresh &&
        _cache != null &&
        _cacheCampaignId == campaignId &&
        _cacheSectionsKey == sectionsKey &&
        _cacheCampanaBancoFilter == campanaKey) {
      return _cache!;
    }

    final sections = sectionFilter ??
        await _campaign.getAvailableSections(campaignId);

    var clients = await _loadClientsDeduped(campaignId, sections);
    clients = applyCampanaBancoFilter(clients, campanaBancoFilter);
    final config = await _loadConfig();
    final gestores = await _firestore.getGestoresActivos();
    final fechaInicio = await _resolveFechaInicio(campaignId);

    final stats = _aggregate(
      clients: clients,
      config: config,
      gestores: gestores,
      fechaInicio: fechaInicio,
      sectionKeys: sections,
    );

    _cache = stats;
    _cacheCampaignId = campaignId;
    _cacheSectionsKey = sectionsKey;
    _cacheCampanaBancoFilter = campanaKey;
    return stats;
  }

  void clearCache() {
    _cache = null;
    _cacheCampaignId = null;
    _cacheSectionsKey = null;
    _cacheCampanaBancoFilter = null;
  }

  Future<List<ClientModel>> _loadClientsDeduped(
    String campaignId,
    List<String> sections,
  ) async {
    final deduped = <String, ClientModel>{};

    Future<void> loadSection(String section) async {
      try {
        final list = await _firestore.getClients(campaignId, section);
        for (final c in list) {
          if (!c.isActiveForGestor) continue;
          final key = c.numeroDocumento.isNotEmpty
              ? c.numeroDocumento
              : '${section}_${c.codigoCliente.isNotEmpty ? c.codigoCliente : c.id}';
          final withSection = _withSectionKey(c, section);
          final existing = deduped[key];
          if (existing == null || !withSection.isPendiente) {
            deduped[key] = withSection;
          }
        }
      } catch (e) {
        debugPrint('CampaignStatsService section $section: $e');
      }
    }

    await Future.wait(sections.map(loadSection));
    return deduped.values.toList();
  }

  ClientModel _withSectionKey(ClientModel c, String section) {
    if (c.seccionKey.isNotEmpty) return c;
    return ClientModel(
      id: c.id,
      campaignId: c.campaignId,
      codigoCliente: c.codigoCliente,
      nombreCompleto: c.nombreCompleto,
      nombres: c.nombres,
      apellidoPaterno: c.apellidoPaterno,
      apellidoMaterno: c.apellidoMaterno,
      numeroDocumento: c.numeroDocumento,
      telefonoMovil: c.telefonoMovil,
      correo: c.correo,
      direccion: c.direccion,
      distrito: c.distrito,
      provincia: c.provincia,
      departamento: c.departamento,
      referencia: c.referencia,
      seccion: c.seccion.isNotEmpty ? c.seccion : section,
      seccionKey: section,
      campanaBanco: c.campanaBanco,
      diasAtraso: c.diasAtraso,
      importeDeudaAsignada: c.importeDeudaAsignada,
      importeDeudaPendiente: c.importeDeudaPendiente,
      estadoGestion: c.estadoGestion,
      notaGestor: c.notaGestor,
      tramoActual: c.tramoActual,
      fechaGestion: c.fechaGestion,
      coordenadaX: c.coordenadaX,
      coordenadaY: c.coordenadaY,
      ubicacionVerificadaLat: c.ubicacionVerificadaLat,
      ubicacionVerificadaLng: c.ubicacionVerificadaLng,
      ubicacionVerificadaGestor: c.ubicacionVerificadaGestor,
      ubicacionVerificadaFecha: c.ubicacionVerificadaFecha,
      cartasGestor: c.cartasGestor,
      fechaPromesaPago: c.fechaPromesaPago,
      montoPromesaPago: c.montoPromesaPago,
      nivel1: c.nivel1,
      nivel2: c.nivel2,
      nivel3: c.nivel3,
      nivel4: c.nivel4,
      canalGestion: c.canalGestion,
      actualizadoPorUid: c.actualizadoPorUid,
      actualizadoPorNombre: c.actualizadoPorNombre,
    );
  }

  Future<CampaignConfigModel> _loadConfig() async {
    try {
      final doc = await _db.collection('configuracion').doc('campana').get();
      return CampaignConfigModel.fromMap(doc.data());
    } catch (e) {
      debugPrint('CampaignStatsService config: $e');
      return const CampaignConfigModel();
    }
  }

  Future<DateTime?> _resolveFechaInicio(String campaignId) async {
    final data = await _campaign.getCampaignData(campaignId);
    if (data == null) return null;
    final raw = data['fecha_inicio'];
    if (raw == null) return null;
    if (raw is Timestamp) return raw.toDate();
    final s = raw.toString();
    if (s.isEmpty) return null;
    return DateTime.tryParse(s) ??
        DateTime.tryParse('${s}T00:00:00');
  }

  CampaignStats _aggregate({
    required List<ClientModel> clients,
    required CampaignConfigModel config,
    required List<UserModel> gestores,
    required DateTime? fechaInicio,
    required List<String> sectionKeys,
  }) {
    final total = clients.length;
    final statusCounts = <String, int>{};
    final tramoCounts = <int, int>{};

    var deudaAsignada = 0.0;
    var deudaPendiente = 0.0;
    var deudaGestionada = 0.0;
    var promesasCount = 0;
    var montoPrometido = 0.0;
    var geolocated = 0;

    for (final c in clients) {
      statusCounts[c.estadoGestion] = (statusCounts[c.estadoGestion] ?? 0) + 1;
      tramoCounts[c.tramoActual] = (tramoCounts[c.tramoActual] ?? 0) + 1;
      deudaAsignada += c.importeDeudaAsignada;
      deudaPendiente += c.importeDeudaPendiente;
      if (!c.isPendiente) {
        deudaGestionada += c.importeDeudaAsignada;
      }
      if (c.hasPromesa) {
        promesasCount++;
        montoPrometido += c.montoPromesaPago;
      }
      if (c.hasVerifiedLocation || c.hasCoordinates) geolocated++;
    }

    final gestionados = total - (statusCounts['pendiente'] ?? 0);
    final avancePct = total > 0 ? gestionados / total * 100 : 0.0;
    final recuperadoBanco =
        (deudaAsignada - deudaPendiente).clamp(0.0, deudaAsignada);
    final tasaRecuperacionBanco =
        deudaAsignada > 0 ? recuperadoBanco / deudaAsignada * 100 : 0.0;

    final pctComision = config.porcentajeComisionJefe;
    final gananciaJefe = recuperadoBanco * (pctComision / 100);

    final today = DateTime.now();
    final start = fechaInicio ?? today;
    final diasTranscurridos =
        today.difference(DateTime(start.year, start.month, start.day)).inDays + 1;
    final duracion = config.duracionDias > 0 ? config.duracionDias : 60;
    final diasRestantes = (duracion - diasTranscurridos).clamp(0, duracion);
    final ritmoDiario =
        diasTranscurridos > 0 ? recuperadoBanco / diasTranscurridos : 0.0;
    var proyeccionLineal = diasTranscurridos > 0
        ? recuperadoBanco * (duracion / diasTranscurridos)
        : recuperadoBanco;
    proyeccionLineal = proyeccionLineal.clamp(0.0, deudaAsignada);
    var proyeccionPromesas = (recuperadoBanco + montoPrometido)
        .clamp(0.0, deudaAsignada);

    final sectionToUid = _buildSectionToUid(gestores);
    final gestorRanking = _buildGestorRanking(
      clients,
      gestores,
      sectionToUid,
    );
    final sectionStats = _buildSectionStats(clients, sectionKeys);
    final deptMaps = _territoryMaps(clients);

    final funnelStages = [
      (label: 'Total asignados', value: total, colorValue: 0),
      (label: 'Gestionados', value: gestionados, colorValue: 1),
      (
        label: 'Habidos',
        value: statusCounts['visitado_habido'] ?? 0,
        colorValue: 2
      ),
      (label: 'Con promesa', value: promesasCount, colorValue: 3),
    ];

    final contactMetrics = computeContactMetrics(clients);
    final campanaBancoBreakdown = buildCampanaBancoBreakdown(clients);

    return CampaignStats(
      clients: clients,
      statusCounts: statusCounts,
      tramoCounts: tramoCounts,
      total: total,
      gestionados: gestionados,
      avancePct: avancePct,
      deudaAsignada: deudaAsignada,
      deudaPendiente: deudaPendiente,
      recuperadoBanco: recuperadoBanco,
      tasaRecuperacionBanco: tasaRecuperacionBanco,
      deudaGestionada: deudaGestionada,
      promesasCount: promesasCount,
      montoPrometido: montoPrometido,
      porcentajeComisionJefe: pctComision,
      gananciaJefe: gananciaJefe,
      diasTranscurridos: diasTranscurridos,
      diasRestantes: diasRestantes,
      ritmoDiarioRecuperacion: ritmoDiario,
      proyeccionLineal: proyeccionLineal,
      proyeccionPromesas: proyeccionPromesas,
      geolocated: geolocated,
      gpsPct: total > 0 ? geolocated / total * 100 : 0,
      gestorRanking: gestorRanking,
      sectionStats: sectionStats,
      topDepartmentsByCount: _topN(deptMaps.counts, 10),
      topDepartmentsByDeuda: _topN(deptMaps.deudas, 10, byValue: true),
      topDistrictsByDeuda: _topN(deptMaps.districts, 10, byValue: true),
      funnelStages: funnelStages,
      contactMetrics: contactMetrics,
      campanaBancoBreakdown: campanaBancoBreakdown,
    );
  }

  Map<String, String> _buildSectionToUid(List<UserModel> gestores) {
    final map = <String, String>{};
    for (final g in gestores) {
      for (final s in g.secciones) {
        if (s.isNotEmpty) map[s] = g.uid;
      }
      if (g.seccion.isNotEmpty) map[g.seccion] = g.uid;
    }
    return map;
  }

  List<GestorRankingEntry> _buildGestorRanking(
    List<ClientModel> clients,
    List<UserModel> gestores,
    Map<String, String> sectionToUid,
  ) {
    final names = {for (final g in gestores) g.uid: g.nombre};
    final buckets = <String, GestorRankingEntry>{};

    void addTo(String uid, String nombre, ClientModel c) {
      final prev = buckets[uid];
      final gestiones = (prev?.gestiones ?? 0) + (c.isPendiente ? 0 : 1);
      final habidos = (prev?.habidos ?? 0) +
          (c.estadoGestion == 'visitado_habido' ? 1 : 0);
      final dg = (prev?.deudaGestionada ?? 0) +
          (c.isPendiente ? 0 : c.importeDeudaAsignada);
      final rec = (prev?.recuperadoBanco ?? 0) + c.recuperadoBanco;
      final pc = (prev?.promesasCount ?? 0) + (c.hasPromesa ? 1 : 0);
      final mp = (prev?.montoPrometido ?? 0) +
          (c.hasPromesa ? c.montoPromesaPago : 0);
      buckets[uid] = GestorRankingEntry(
        uid: uid,
        nombre: nombre,
        gestiones: gestiones,
        habidos: habidos,
        deudaGestionada: dg,
        recuperadoBanco: rec,
        promesasCount: pc,
        montoPrometido: mp,
      );
    }

    for (final c in clients) {
      if (c.isPendiente) continue;
      String uid = c.actualizadoPorUid;
      var nombre = c.actualizadoPorNombre;
      if (uid.isEmpty) {
        uid = sectionToUid[c.seccionKey] ?? '';
      }
      if (uid.isEmpty) {
        uid = '_sin_atribuir';
        nombre = 'Sin atribuir';
      }
      if (nombre.isEmpty) nombre = names[uid] ?? uid;
      addTo(uid, nombre, c);
    }

    final list = buckets.values.toList()
      ..sort((a, b) => b.recuperadoBanco.compareTo(a.recuperadoBanco));
    return list.take(10).toList();
  }

  List<SectionStatsEntry> _buildSectionStats(
    List<ClientModel> clients,
    List<String> sectionKeys,
  ) {
    final bySection = <String, List<ClientModel>>{};
    for (final key in sectionKeys) {
      bySection[key] = [];
    }
    for (final c in clients) {
      final k = c.seccionKey.isNotEmpty ? c.seccionKey : c.seccion;
      bySection.putIfAbsent(k, () => []).add(c);
    }

    final entries = <SectionStatsEntry>[];
    for (final entry in bySection.entries) {
      final list = entry.value;
      final total = list.length;
      final visitados = list.where((c) => !c.isPendiente).length;
      entries.add(SectionStatsEntry(
        seccion: entry.key,
        total: total,
        visitados: visitados,
        pendientes: total - visitados,
        deuda: list.fold(0.0, (s, c) => s + c.importeDeudaAsignada),
        deudaGestionada: list
            .where((c) => !c.isPendiente)
            .fold(0.0, (s, c) => s + c.importeDeudaAsignada),
        recuperadoBanco: list.fold(0.0, (s, c) => s + c.recuperadoBanco),
        geolocated: list
            .where((c) => c.hasVerifiedLocation || c.hasCoordinates)
            .length,
      ));
    }
    entries.sort((a, b) => a.seccion.compareTo(b.seccion));
    return entries;
  }

  ({Map<String, double> counts, Map<String, double> deudas, Map<String, double> districts})
      _territoryMaps(List<ClientModel> clients) {
    final counts = <String, double>{};
    final deudas = <String, double>{};
    final districts = <String, double>{};
    for (final c in clients) {
      final dept = c.departamento.isNotEmpty ? c.departamento : 'Sin Depto.';
      counts[dept] = (counts[dept] ?? 0) + 1;
      deudas[dept] = (deudas[dept] ?? 0) + c.importeDeudaAsignada;
      final dist = c.distrito.isNotEmpty ? c.distrito : 'Sin Distrito';
      districts[dist] = (districts[dist] ?? 0) + c.importeDeudaAsignada;
    }
    return (counts: counts, deudas: deudas, districts: districts);
  }

  List<StatsBarItem> _topN(
    Map<String, double> map,
    int n, {
    bool byValue = false,
  }) {
    final items = map.entries
        .map((e) => StatsBarItem(
              label: e.key,
              value: e.value,
              count: e.value.toInt(),
            ))
        .toList();
    if (byValue) {
      items.sort((a, b) => b.value.compareTo(a.value));
    } else {
      items.sort((a, b) => b.count.compareTo(a.count));
    }
    return items.take(n).toList();
  }
}
