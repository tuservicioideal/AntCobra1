import '../models/user_model.dart';

/// Claves de sección Firestore (`gestores/{id}`) para un perfil de gestor.
/// Prioriza el array [UserModel.secciones] y construye la clave compuesta
/// `region_zona_seccion` cuando existen los tres campos legacy.
List<String> resolveGestorSectionKeys(UserModel? profile) {
  if (profile == null) return [];

  final keys = <String>{};
  for (final raw in profile.secciones) {
    final k = raw.trim();
    if (k.isNotEmpty) keys.add(k);
  }

  final region = profile.region.trim();
  final zona = profile.zona.trim();
  final seccion = profile.seccion.trim();

  if (region.isNotEmpty && zona.isNotEmpty && seccion.isNotEmpty) {
    keys.add('${region}_${zona}_$seccion');
  } else if (seccion.contains('_')) {
    keys.add(seccion);
  }

  final sorted = keys.toList()..sort();
  return sorted;
}

/// Si no hay claves explícitas, intenta emparejar por letra de sección en la campaña.
List<String> resolveGestorSectionKeysForCampaign(
  UserModel? profile,
  List<String> campaignSectionIds,
) {
  final keys = resolveGestorSectionKeys(profile);
  if (keys.isNotEmpty) return keys;

  final seccion = profile?.seccion.trim() ?? '';
  if (seccion.isEmpty) return [];

  final matches = campaignSectionIds.where((id) {
    if (id == seccion) return true;
    final parts = id.split('_');
    return parts.isNotEmpty && parts.last == seccion;
  }).toList()
    ..sort();
  return matches;
}

/// Sección reservada para el pool de reasignación central.
const String poolReasignacionSectionKey = '_POOL_REASIGNACION';

/// Sección reservada para cuentas derivadas a gestión especial.
const String gestionEspecialSectionKey = '_GESTION_ESPECIAL';

/// Secciones que no son destino válido de cartera activa.
bool isReservedReassignmentSection(String key) {
  return key == poolReasignacionSectionKey ||
      key == gestionEspecialSectionKey;
}

/// UID del operador call embebido en `_CALL_{uid}`.
String? callSectionUid(String sectionKey) {
  if (!sectionKey.startsWith('_CALL_')) return null;
  final uid = sectionKey.substring(6);
  return uid.isEmpty ? null : uid;
}

/// Clave de sección Firestore para un gestor call.
String callSectionKeyForUid(String uid) => '_CALL_$uid';

/// Etiqueta legible para una clave compuesta `01_1211_H`.
String sectionDisplayLabel(String key) {
  // Mantener etiqueta histórica usada en mapa/stats del gestor call.
  if (key.startsWith('_CALL_')) return 'Mi cartera call';
  if (key == poolReasignacionSectionKey) return 'Pool de reasignación';
  if (key == gestionEspecialSectionKey) return 'Gestión especial';
  final parts = key.split('_');
  if (parts.length == 3) {
    return 'R${parts[0]} · Z${parts[1]} · Sección ${parts[2]}';
  }
  return key;
}

/// Sección destino principal de un gestor (call o primera territorial).
String primaryDestinationSection(UserModel gestor) {
  if (gestor.isCallGestor) {
    return callSectionKeyForUid(gestor.uid);
  }
  final keys = resolveGestorSectionKeys(gestor);
  if (keys.isNotEmpty) return keys.first;
  return gestor.seccion;
}

/// Resuelve UID del gestor dueño de una sección.
String? resolveGestorUidForSection(String seccionKey, List<UserModel> users) {
  final callUid = callSectionUid(seccionKey);
  if (callUid != null) return callUid;
  for (final user in users) {
    if (!user.activo) continue;
    final keys = resolveGestorSectionKeys(user);
    if (keys.contains(seccionKey)) return user.uid;
  }
  return null;
}

/// Etiqueta de gestor + sección para pickers de reasignación.
String gestorDestinationLabel(UserModel gestor, String sectionKey) {
  final canal = gestor.isCallGestor ? 'Call' : 'Campo';
  return '${gestor.nombre} ($canal) · ${sectionDisplayLabel(sectionKey)}';
}
