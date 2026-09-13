/// Extrae texto de varios orígenes (exception, stack, console.error).
String combineErrorSources(Iterable<Object?> parts) {
  final out = StringBuffer();
  for (final part in parts) {
    if (part == null) continue;
    final text = part.toString().trim();
    if (text.isEmpty) continue;
    if (out.isNotEmpty) out.writeln();
    out.write(text);
  }
  return out.toString();
}

/// Detecta el assertion interno del SDK JS de Firestore (ca9 / b815).
/// Tras ese fallo el cliente queda inservible hasta recargar la página.
bool isFirestoreInternalAssertion(Object? error) {
  final msg = error?.toString() ?? '';
  if (msg.isEmpty) return false;
  final lower = msg.toLowerCase();
  if (lower.contains('internal assertion failed')) return true;
  if (RegExp(r'\(ID:\s*(ca9|b815)\)').hasMatch(msg)) return true;
  if (lower.contains('@firebase/firestore') &&
      (msg.contains('ca9') || msg.contains('b815'))) {
    return true;
  }
  return false;
}

/// Evita un bucle de recarga si el assertion vuelve a ocurrir al instante.
bool shouldReloadAfterFirestoreAssertion({required bool alreadyReloadedThisSession}) {
  return !alreadyReloadedThisSession;
}
