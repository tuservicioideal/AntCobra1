import '../models/client_model.dart';
import 'campana_banco_utils.dart';
import 'client_list_pagination.dart';
import 'tramo_filter.dart';

/// Clientes visibles en Mapa: cartera completa o solo los enviados desde Perfil.
List<ClientModel> filterMapClientList({
  required List<ClientModel> clients,
  required String? campanaFilter,
  required String query,
  required bool restrictToProfileCandidates,
  String? selectedSection,
  String? allSectionsKey,
  Set<String>? candidateIds,
  Set<int> tramoFilter = const {},
}) {
  var base = applyCampanaBancoFilter(clients, campanaFilter);
  if (restrictToProfileCandidates) {
    if (selectedSection != null &&
        selectedSection.isNotEmpty &&
        selectedSection != allSectionsKey) {
      base = base
          .where(
            (c) =>
                c.seccionKey == selectedSection || c.seccion == selectedSection,
          )
          .toList();
    }
  } else if (candidateIds != null && candidateIds.isNotEmpty) {
    base = base.where((c) => candidateIds.contains(c.id)).toList();
  }
  base = applyTramoFilter(base, tramoFilter);
  if (query.trim().isEmpty) return base;
  return base.where((c) => matchesClientSearch(c, query)).toList();
}
