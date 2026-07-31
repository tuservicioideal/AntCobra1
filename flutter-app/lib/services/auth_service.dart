import 'package:flutter/foundation.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import '../models/user_model.dart';

/// Authentication service with multi-source profile resolution.
/// Prefers canonical `usuarios/{uid}`; never silently treats users as gestores.
class AuthService extends ChangeNotifier {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final FirebaseFunctions _functions =
      FirebaseFunctions.instanceFor(region: 'us-central1');

  User? _firebaseUser;
  UserModel? _profile;
  bool _loading = true;
  String? _error;
  Future<void>? _profileResolveFuture;
  String? _profileResolveUid;

  AuthService() {
    _auth.authStateChanges().listen(_onAuthStateChanged);
  }

  User? get firebaseUser => _firebaseUser;
  UserModel? get profile => _profile;
  bool get loading => _loading;
  bool get isAuthenticated => _firebaseUser != null && _profile != null;
  String? get error => _error;

  // Role helpers
  bool get isAdmin => _profile?.isAdmin ?? false;
  bool get isSupervisor => _profile?.isSupervisor ?? false;
  bool get isAsistente => _profile?.isAsistente ?? false;
  bool get canManageUsers => _profile?.canManageUsers ?? false;
  bool get canViewStats => _profile?.canViewStats ?? false;

  Future<void> _onAuthStateChanged(User? user) async {
    _firebaseUser = user;
    if (user != null) {
      await _resolveProfileOnce(user);
    } else {
      _profile = null;
      _error = null;
    }
    _loading = false;
    notifyListeners();
  }

  Future<DocumentSnapshot<Map<String, dynamic>>?> _safeGetDoc(
    DocumentReference<Map<String, dynamic>> ref,
  ) async {
    try {
      return await ref.get().timeout(const Duration(seconds: 15));
    } catch (e) {
      debugPrint('Safe get failed (${ref.path}): $e');
      return null;
    }
  }

  Future<QuerySnapshot<Map<String, dynamic>>?> _safeQuery(
    Query<Map<String, dynamic>> query,
  ) async {
    try {
      return await query.get().timeout(const Duration(seconds: 15));
    } catch (e) {
      debugPrint('Safe query failed: $e');
      return null;
    }
  }

  Future<void> _resolveProfileOnce(User user) {
    if (_profileResolveUid == user.uid && _profileResolveFuture != null) {
      return _profileResolveFuture!;
    }
    _profileResolveUid = user.uid;
    _profileResolveFuture = _resolveProfile(user).whenComplete(() {
      _profileResolveFuture = null;
      _profileResolveUid = null;
    });
    return _profileResolveFuture!;
  }

  Future<void> _failIncompleteProfile(String message) async {
    debugPrint('Incomplete profile: $message');
    _error = message;
    _profile = null;
    try {
      await _auth.signOut();
    } catch (e) {
      debugPrint('Sign out after incomplete profile failed: $e');
    }
  }

  /// Ensures `usuarios/{uid}` exists via Admin SDK (callable), copying legacy if needed.
  Future<Map<String, dynamic>?> _ensureCanonicalProfile() async {
    try {
      final callable = _functions.httpsCallable('ensureCanonicalUserProfile');
      final result = await callable.call().timeout(const Duration(seconds: 20));
      final data = result.data;
      if (data is Map) {
        final profile = data['profile'];
        if (profile is Map) {
          return Map<String, dynamic>.from(profile);
        }
      }
    } catch (e) {
      debugPrint('ensureCanonicalUserProfile failed: $e');
    }
    return null;
  }

  Future<void> _resolveProfile(User user) async {
    final email = (user.email ?? '').trim();
    final emailLower = email.toLowerCase();

    try {
      Map<String, dynamic>? profileData;
      var fromCanonical = false;

      // 1. Direct UID doc (always preferred)
      final uidDoc = await _safeGetDoc(_db.collection('usuarios').doc(user.uid));
      if (uidDoc?.exists == true && uidDoc!.data() != null) {
        profileData = uidDoc.data()!;
        fromCanonical = true;
      }

      // 2. Missing canonical → Cloud Function sync from legacy / repair
      if (profileData == null) {
        final ensured = await _ensureCanonicalProfile();
        if (ensured != null) {
          profileData = ensured;
          fromCanonical = true;
        }
      }

      // 3. Fallback read: email field / email-derived ID (read-only for UI hint;
      //    still require ensure so rules see usuarios/{uid})
      if (profileData == null && emailLower.isNotEmpty) {
        final emailQuery = await _safeQuery(
          _db
              .collection('usuarios')
              .where('email', isEqualTo: emailLower)
              .limit(1),
        );
        if (emailQuery != null && emailQuery.docs.isNotEmpty) {
          profileData = emailQuery.docs.first.data();
        }
      }

      if (profileData == null && emailLower.isNotEmpty) {
        final emailId = emailLower.replaceAll(RegExp(r'[^a-zA-Z0-9]'), '_');
        final emailDoc = await _safeGetDoc(_db.collection('usuarios').doc(emailId));
        if (emailDoc?.exists == true && emailDoc!.data() != null) {
          profileData = emailDoc.data()!;
        }
      }

      if (profileData == null) {
        await _failIncompleteProfile(
          'Tu perfil no está configurado. Contacta al administrador.',
        );
        return;
      }

      if (profileData['activo'] == false) {
        await _failIncompleteProfile(
          'Tu cuenta ha sido desactivada. Contacta al administrador.',
        );
        return;
      }

      final rol = profileData['rol']?.toString().trim() ?? '';
      if (rol.isEmpty) {
        await _failIncompleteProfile(
          'Tu perfil no tiene rol asignado. Contacta al administrador.',
        );
        return;
      }

      // If we only have a legacy doc in memory, try ensure once more so rules work.
      if (!fromCanonical) {
        final ensured = await _ensureCanonicalProfile();
        if (ensured != null) {
          profileData = ensured;
        } else {
          await _failIncompleteProfile(
            'No se pudo sincronizar tu perfil. Contacta al administrador.',
          );
          return;
        }
      }

      _profile = UserModel.fromMap(user.uid, profileData);
      _error = null;
    } catch (e) {
      debugPrint('Error resolving profile: $e');
      await _failIncompleteProfile(
        'No se pudo cargar tu perfil. Intenta de nuevo o contacta al administrador.',
      );
    }
  }

  /// Sign in with email and password.
  Future<bool> signIn(String email, String password) async {
    try {
      _error = null;
      notifyListeners();
      await _auth.signInWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );
      // authStateChanges may not fire if the session was already active.
      final user = _auth.currentUser;
      if (user != null) {
        _firebaseUser = user;
        await _resolveProfileOnce(user);
      }
      notifyListeners();
      return isAuthenticated;
    } on FirebaseAuthException catch (e) {
      switch (e.code) {
        case 'user-not-found':
          _error = 'Usuario no encontrado';
          break;
        case 'wrong-password':
          _error = 'Contraseña incorrecta';
          break;
        case 'invalid-email':
          _error = 'Correo electrónico inválido';
          break;
        case 'user-disabled':
          _error = 'Cuenta deshabilitada';
          break;
        case 'too-many-requests':
          _error = 'Demasiados intentos. Intente más tarde';
          break;
        case 'invalid-credential':
          _error = 'Credenciales inválidas';
          break;
        default:
          _error = 'Error de autenticación: ${e.message}';
      }
      notifyListeners();
      return false;
    } catch (e) {
      _error = 'Error inesperado: $e';
      notifyListeners();
      return false;
    }
  }

  /// Sign out.
  Future<void> signOut() async {
    await _auth.signOut();
    _profile = null;
    notifyListeners();
  }

  /// Refresh profile from Firestore.
  Future<void> refreshProfile() async {
    if (_firebaseUser != null) {
      await _resolveProfileOnce(_firebaseUser!);
      notifyListeners();
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
