import 'package:intl/intl.dart';

import '../models/client_model.dart';
import '../models/gestor_stats.dart';
import '../models/user_model.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/section_utils.dart';
import 'campaign_service.dart';
import 'firestore_service.dart';

/// Carga clientes de campaña y KPIs del gestor autenticado.
class GestorStatsService {
  final CampaignService _campaignService;
  final FirestoreService _firestoreService;
  final DateFormat _dateFmt = DateFormat('yyyy-MM-dd');

  GestorStatsService({
    CampaignService? campaignService,
    FirestoreService? firestoreService,
  })  : _campaignService = campaignService ?? CampaignService(),
        _firestoreService = firestoreService ?? FirestoreService();

  /// Clientes activos del gestor sin filtro de campaña del banco.
  Future<List<ClientModel>> loadActiveClientsForProfile(
    UserModel profile,
  ) async {
    final clients = await _loadClientsForProfile(profile);
    if (clients == null) return [];
    return clients.where((c) => c.isActiveForGestor).toList();
  }

  /// Devuelve estadísticas o `null` si no hay campaña activa o secciones.
  Future<GestorStats?> loadForProfile(
    UserModel profile, {
    String? campanaBancoFilter,
  }) async {
    final clients = await _loadClientsForProfile(profile);
    if (clients == null) return null;

    final today = _dateFmt.format(DateTime.now());
    final rutaHoy = await _firestoreService.getMyRouteByDate(today);

    var active = clients.where((c) => c.isActiveForGestor).toList();
    active = applyCampanaBancoFilter(active, campanaBancoFilter);
    return GestorStats.fromClients(active, rutaHoy: rutaHoy);
  }

  Future<List<ClientModel>?> _loadClientsForProfile(UserModel profile) async {
    final campaignId = await _campaignService.getActiveCampaignId();
    if (campaignId == null) return null;

    var sectionKeys = resolveGestorSectionKeys(profile);
    if (sectionKeys.isEmpty) {
      final allSections =
          await _campaignService.getAvailableSections(campaignId);
      sectionKeys = resolveGestorSectionKeysForCampaign(profile, allSections);
    }
    if (sectionKeys.isEmpty) return null;

    if (sectionKeys.length == 1) {
      return _firestoreService.getClients(campaignId, sectionKeys.first);
    }
    return _firestoreService.getClientsMultiSection(campaignId, sectionKeys);
  }
}
