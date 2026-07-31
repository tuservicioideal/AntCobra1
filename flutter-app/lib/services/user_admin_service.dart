import 'package:cloud_functions/cloud_functions.dart';
import 'package:flutter/foundation.dart';

import '../utils/user_admin_utils.dart';

/// Admin user provisioning via Cloud Functions (mirrors admin-app firebase_service).
class UserAdminService {
  final FirebaseFunctions _functions;

  UserAdminService({FirebaseFunctions? functions})
      : _functions = functions ??
            FirebaseFunctions.instanceFor(region: 'us-central1');

  Future<String> createGestorUser({
    required String email,
    required String password,
    required String nombre,
    String telefono = '',
    String seccion = '',
    String zona = '',
    String region = '',
    String rol = 'gestor',
    List<String>? secciones,
    String canal = 'campo',
  }) async {
    final normalized = normalizeRoleCanal(rol, canal);
    final built = buildSecciones(
      rol: normalized.rol,
      canal: normalized.canal,
      secciones: secciones,
      seccion: seccion,
      region: region,
      zona: zona,
    );

    try {
      final callable = _functions.httpsCallable(
        'createGestorUser',
        options: HttpsCallableOptions(timeout: const Duration(seconds: 30)),
      );
      final result = await callable.call<Map<String, dynamic>>({
        'email': email.trim().toLowerCase(),
        'password': password,
        'nombre': nombre.trim(),
        'telefono': telefono.trim(),
        'seccion': built.seccion,
        'zona': built.zona,
        'region': built.region,
        'rol': normalized.rol,
        'canal': normalized.canal,
        'secciones': built.secciones,
      });

      final data = result.data;
      final uid = data['uid']?.toString() ?? '';
      if (uid.isEmpty) {
        throw Exception('No se recibió UID del servidor.');
      }
      return uid;
    } catch (e, st) {
      debugPrint('createGestorUser error: $e\n$st');
      throw Exception(mapUserAdminError(e));
    }
  }

  Future<void> updateGestorUser({
    required String uid,
    Map<String, dynamic> updates = const {},
    String? password,
  }) async {
    final payload = Map<String, dynamic>.from(updates);
    if (password != null && password.trim().isNotEmpty) {
      payload['password'] = password.trim();
    }

    try {
      final callable = _functions.httpsCallable(
        'updateGestorUser',
        options: HttpsCallableOptions(timeout: const Duration(seconds: 30)),
      );
      await callable.call<Map<String, dynamic>>({
        'uid': uid,
        'updates': payload,
      });
    } catch (e, st) {
      debugPrint('updateGestorUser error: $e\n$st');
      throw Exception(mapUserAdminError(e));
    }
  }

  Future<void> deleteGestorUser(String uid) async {
    try {
      final callable = _functions.httpsCallable(
        'deleteGestorUser',
        options: HttpsCallableOptions(timeout: const Duration(seconds: 30)),
      );
      await callable.call<Map<String, dynamic>>({'uid': uid});
    } catch (e, st) {
      debugPrint('deleteGestorUser error: $e\n$st');
      throw Exception(mapUserAdminError(e));
    }
  }
}
