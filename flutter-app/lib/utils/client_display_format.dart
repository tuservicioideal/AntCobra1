// Presentation helpers for client detail UI.

String formatAddressDisplay(String raw) {
  var s = raw.trim();
  if (s.startsWith('.')) s = s.substring(1).trim();
  s = s.replaceAll(RegExp(r'\s+'), ' ');
  if (s.isEmpty) return s;
  return _toTitleCase(s);
}

String _normalizeForCompare(String s) {
  return s
      .toLowerCase()
      .replaceAll(RegExp(r'[^a-z0-9áéíóúñü\s]'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
}

/// True when [referencia] is empty or already contained in [direccion].
bool referenceRedundant(String direccion, String referencia) {
  final ref = referencia.trim();
  if (ref.isEmpty) return true;
  final dir = _normalizeForCompare(direccion);
  final r = _normalizeForCompare(ref);
  if (r.length < 4) return false;
  return dir.contains(r);
}

String shortClientTitle(String displayName, String codigoCliente) {
  if (codigoCliente.isNotEmpty) return codigoCliente;
  final words = displayName.split(' ').where((w) => w.isNotEmpty).toList();
  if (words.length >= 2) {
    return '${words[words.length - 2]} ${words.last}';
  }
  if (displayName.length > 22) {
    return '${displayName.substring(0, 22)}…';
  }
  return displayName;
}

String locationSubtitle(String distrito, String departamento) {
  return [distrito, departamento].where((s) => s.trim().isNotEmpty).join(' · ');
}

String _toTitleCase(String input) {
  return input.split(' ').map((word) {
    if (word.isEmpty) return word;
    if (word == word.toUpperCase() && word.length > 2) {
      return '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}';
    }
    if (word.length == 1) return word.toUpperCase();
    return '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}';
  }).join(' ');
}
