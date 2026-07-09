/// Pure helpers for user administration (mirrors admin-app / Cloud Functions logic).

const validUserRoles = ['gestor', 'asistente', 'supervisor', 'admin'];
const validCanales = ['campo', 'call'];

class RoleCanal {
  final String rol;
  final String canal;

  const RoleCanal({required this.rol, required this.canal});
}

class BuiltSecciones {
  final List<String> secciones;
  final String region;
  final String zona;
  final String seccion;

  const BuiltSecciones({
    required this.secciones,
    required this.region,
    required this.zona,
    required this.seccion,
  });
}

/// Normalize role and canal (mirrors firebase_service.py).
RoleCanal normalizeRoleCanal(String? rol, String? canal) {
  var normalizedRol = (rol ?? 'gestor').trim().toLowerCase();
  if (!validUserRoles.contains(normalizedRol)) {
    normalizedRol = 'gestor';
  }

  var normalizedCanal = (canal ?? 'campo').trim().toLowerCase();
  if (!validCanales.contains(normalizedCanal)) {
    normalizedCanal = 'campo';
  }

  if (normalizedRol != 'gestor') {
    normalizedCanal = 'campo';
  }

  return RoleCanal(rol: normalizedRol, canal: normalizedCanal);
}

bool isCallGestorRole(String rol, String canal) =>
    rol == 'gestor' && canal == 'call';

bool shouldShowCanalSelector(String rol) => rol == 'gestor';

bool shouldShowTerritorialPicker(String rol, String canal) {
  if (rol == 'admin' || rol == 'supervisor') return false;
  if (isCallGestorRole(rol, canal)) return false;
  return true;
}

bool requiresTerritorialSections(String rol, String canal) {
  if (rol == 'asistente') return true;
  if (rol == 'gestor' && !isCallGestorRole(rol, canal)) return true;
  return false;
}

/// Build secciones list (mirrors firebase_service.py create_gestor_user).
BuiltSecciones buildSecciones({
  required String rol,
  required String canal,
  List<String>? secciones,
  String seccion = '',
  String region = '',
  String zona = '',
  String? uid,
}) {
  final normalizedSeccion = seccion.trim().toUpperCase();
  var finalRegion = region.trim();
  var finalZona = zona.trim();
  var finalSeccion = normalizedSeccion;
  var finalSecciones = <String>[];

  if (isCallGestorRole(rol, canal)) {
    if (uid != null && uid.isNotEmpty) {
      finalSecciones = ['_CALL_$uid'];
    }
    return BuiltSecciones(
      secciones: finalSecciones,
      region: finalRegion,
      zona: finalZona,
      seccion: finalSeccion,
    );
  }

  if (secciones != null && secciones.isNotEmpty) {
    finalSecciones = secciones
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toSet()
        .toList()
      ..sort();
    if (finalSecciones.isNotEmpty) {
      final parts = finalSecciones.first.split('_');
      if (parts.length == 3) {
        if (finalRegion.isEmpty) finalRegion = parts[0];
        if (finalZona.isEmpty) finalZona = parts[1];
        if (finalSeccion.isEmpty) finalSeccion = parts[2].toUpperCase();
      }
    }
  } else if (finalRegion.isNotEmpty &&
      finalZona.isNotEmpty &&
      finalSeccion.isNotEmpty) {
    finalSecciones = ['${finalRegion}_${finalZona}_$finalSeccion'];
  } else if (finalSeccion.isNotEmpty) {
    finalSecciones = [finalSeccion];
  }

  return BuiltSecciones(
    secciones: finalSecciones,
    region: finalRegion,
    zona: finalZona,
    seccion: finalSeccion,
  );
}

String? validateUserForm({
  required bool isEdit,
  required String nombre,
  required String email,
  required String password,
  required String rol,
  required String canal,
  required List<String> selectedSecciones,
}) {
  if (nombre.trim().isEmpty) {
    return 'El nombre es obligatorio.';
  }
  if (email.trim().isEmpty) {
    return 'El correo electrónico es obligatorio.';
  }
  if (!isEdit && password.trim().length < 6) {
    return 'La contraseña debe tener al menos 6 caracteres.';
  }
  if (isEdit && password.isNotEmpty && password.trim().length < 6) {
    return 'La contraseña debe tener al menos 6 caracteres.';
  }
  if (requiresTerritorialSections(rol, canal) && selectedSecciones.isEmpty) {
    return 'Gestores de campo y asistentes requieren al menos una sección.';
  }
  return null;
}

String mapUserAdminError(Object error) {
  final message = error.toString();
  if (message.contains('already-exists') ||
      message.contains('email-already-exists') ||
      message.contains('email-already-in-use')) {
    return 'Ya existe un usuario con ese correo electrónico.';
  }
  if (message.contains('weak-password') ||
      message.contains('invalid-password')) {
    return 'La contraseña es demasiado débil.';
  }
  if (message.contains('permission-denied')) {
    return 'No tienes permiso para gestionar usuarios.';
  }
  if (message.contains('unauthenticated')) {
    return 'Debes iniciar sesión.';
  }
  if (message.contains('not-found') || message.contains('NOT_FOUND')) {
    return 'Función no disponible. Despliega Cloud Functions (createGestorUser).';
  }
  if (message.contains('invalid-argument')) {
    final match = RegExp(r'message:\s*(.+?)(?:,|\])').firstMatch(message);
    if (match != null) return match.group(1)!.trim();
  }
  return 'Error al procesar la solicitud. Intenta de nuevo.';
}
