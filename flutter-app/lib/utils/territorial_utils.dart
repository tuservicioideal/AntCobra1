import '../models/user_model.dart';

/// Parsed components of a composite section key (`region_zona_seccion`).
class TerritorialParts {
  final String region;
  final String zona;
  final String seccionLetter;

  const TerritorialParts({
    required this.region,
    required this.zona,
    required this.seccionLetter,
  });

  bool get isComplete =>
      region.isNotEmpty && zona.isNotEmpty && seccionLetter.isNotEmpty;
}

/// Parses `01_1211_H` into region, zona and section letter.
TerritorialParts? parseCompositeSectionKey(String key) {
  final trimmed = key.trim();
  if (trimmed.isEmpty) return null;

  final parts = trimmed.split('_');
  if (parts.length != 3) return null;

  final region = parts[0].trim();
  final zona = parts[1].trim();
  final seccionLetter = parts[2].trim().toUpperCase();
  if (region.isEmpty || zona.isEmpty || seccionLetter.isEmpty) return null;

  return TerritorialParts(
    region: region,
    zona: zona,
    seccionLetter: seccionLetter,
  );
}

/// Builds composite key `region_zona_seccion` (section letter uppercased).
String buildCompositeSectionKey(String region, String zona, String seccion) {
  final r = region.trim();
  final z = zona.trim();
  final s = seccion.trim().toUpperCase();
  if (r.isEmpty || z.isEmpty || s.isEmpty) return '';
  return '${r}_${z}_$s';
}

/// Resolves the best composite key for pre-filling the territorial picker.
String resolveInitialCompositeKey(UserModel? user) {
  if (user == null) return '';

  for (final raw in user.secciones) {
    final key = raw.trim();
    if (key.isNotEmpty) return key;
  }

  final fromFields = buildCompositeSectionKey(
    user.region,
    user.zona,
    user.seccion,
  );
  if (fromFields.isNotEmpty) return fromFields;

  final seccion = user.seccion.trim();
  if (seccion.contains('_')) return seccion;

  return '';
}

/// Human-readable territorial label for a user card or profile summary.
String userTerritorialLabel(UserModel user) {
  final composite = resolveInitialCompositeKey(user);
  if (composite.isNotEmpty) {
    final parts = parseCompositeSectionKey(composite);
    if (parts != null) {
      return 'R${parts.region} · Z${parts.zona} · Sección ${parts.seccionLetter}';
    }
    return composite;
  }

  if (user.seccion.isNotEmpty) return 'Sección ${user.seccion}';
  return '';
}

/// Groups composite keys as Región → Zona → [composite keys].
/// Non-composite keys (e.g. `_CALL_…`) are omitted.
Map<String, Map<String, List<String>>> groupSeccionesByHierarchy(
  Iterable<String> keys,
) {
  final result = <String, Map<String, List<String>>>{};
  for (final raw in keys) {
    final parts = parseCompositeSectionKey(raw);
    if (parts == null) continue;
    final key = buildCompositeSectionKey(
      parts.region,
      parts.zona,
      parts.seccionLetter,
    );
    if (key.isEmpty) continue;
    final zonas = result.putIfAbsent(parts.region, () => {});
    final secs = zonas.putIfAbsent(parts.zona, () => <String>[]);
    if (!secs.contains(key)) secs.add(key);
  }
  for (final zonas in result.values) {
    for (final secs in zonas.values) {
      secs.sort();
    }
  }
  return Map.fromEntries(
    result.entries.toList()..sort((a, b) => a.key.compareTo(b.key)),
  );
}

/// Removes every composite key belonging to [region].
List<String> removeRegion(List<String> keys, String region) {
  final r = region.trim();
  return keys.where((k) {
    final parts = parseCompositeSectionKey(k);
    if (parts == null) return true;
    return parts.region != r;
  }).toList();
}

/// Removes every composite key belonging to [region]/[zona].
List<String> removeZona(List<String> keys, String region, String zona) {
  final r = region.trim();
  final z = zona.trim();
  return keys.where((k) {
    final parts = parseCompositeSectionKey(k);
    if (parts == null) return true;
    return parts.region != r || parts.zona != z;
  }).toList();
}

/// Removes a single composite (or exact) key.
List<String> removeSeccion(List<String> keys, String key) {
  final target = key.trim();
  return keys.where((k) => k.trim() != target).toList();
}

/// How many composite keys match a region.
int countSeccionesInRegion(Iterable<String> keys, String region) {
  final r = region.trim();
  return keys.where((k) {
    final parts = parseCompositeSectionKey(k);
    return parts != null && parts.region == r;
  }).length;
}

/// How many composite keys match a region+zona.
int countSeccionesInZona(
  Iterable<String> keys,
  String region,
  String zona,
) {
  final r = region.trim();
  final z = zona.trim();
  return keys.where((k) {
    final parts = parseCompositeSectionKey(k);
    return parts != null && parts.region == r && parts.zona == z;
  }).length;
}

/// Derives legacy `region` / `zona` / `seccion` from the first remaining key.
TerritorialParts legacyFieldsFromSecciones(Iterable<String> keys) {
  for (final raw in keys) {
    final parts = parseCompositeSectionKey(raw);
    if (parts != null) return parts;
  }
  return const TerritorialParts(region: '', zona: '', seccionLetter: '');
}
