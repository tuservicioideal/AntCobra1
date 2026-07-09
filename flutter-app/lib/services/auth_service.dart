import 'package:flutter/foundation.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user_model.dart';

/// Authentication service with multi-source profile resolution.
/// Mirrors the gestor-app useAuth.js logic: searches by UID, email field,
/// and email-derived ID to find the user profile.
class AuthService extends ChangeNotifier {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _db = FirebaseFirestore.instance;

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

  /// Multi-source profile resolution (mirrors useAuth.js).
  /// 1. Try direct UID doc
  /// 2. Search by email field (case-insensitive)
  /// 3. Try email-derived doc ID
  /// If found via secondary source, sync to UID doc.
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

  UserModel _minimalProfile(User user) {
    final email = (user.email ?? '').trim();
    return UserModel(
      uid: user.uid,
      email: email,
      nombre: user.displayName ?? (email.isNotEmpty ? email.split('@').first : 'Usuario'),
      rol: 'gestor',
    );
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

  Future<void> _resolveProfile(User user) async {
    final email = (user.email ?? '').trim();
    final emailLower = email.toLowerCase();

    try {
      Map<String, dynamic>? profileData;
      String? sourceDocId;

      // 1. Direct UID doc
      final uidDoc = await _safeGetDoc(_db.collection('usuarios').doc(user.uid));
      if (uidDoc?.exists == true && uidDoc!.data() != null) {
        profileData = uidDoc.data()!;
        sourceDocId = user.uid;
      }

      // 2. Search by email field (lowercase)
      if (profileData == null && emailLower.isNotEmpty) {
        final emailQuery = await _safeQuery(
          _db
              .collection('usuarios')
              .where('email', isEqualTo: emailLower)
              .limit(1),
        );
        if (emailQuery != null && emailQuery.docs.isNotEmpty) {
          profileData = emailQuery.docs.first.data();
          sourceDocId = emailQuery.docs.first.id;
        }
      }

      // 3. Try email-derived doc ID
      if (profileData == null && emailLower.isNotEmpty) {
        final emailId = emailLower.replaceAll(RegExp(r'[^a-zA-Z0-9]'), '_');
        final emailDoc = await _safeGetDoc(_db.collection('usuarios').doc(emailId));
        if (emailDoc?.exists == true && emailDoc!.data() != null) {
          profileData = emailDoc.data()!;
          sourceDocId = emailId;
        }
      }

      if (profileData != null) {
        if (profileData['activo'] == false) {
          debugPrint('User account is deactivated');
          _error = 'Tu cuenta ha sido desactivada. Contacta al administrador.';
          _profile = null;
          await _auth.signOut();
          return;
        }

        _profile = UserModel.fromMap(user.uid, profileData);
        _error = null;

        // Sync to canonical UID doc when found elsewhere (non-blocking).
        if (sourceDocId != null && sourceDocId != user.uid) {
          try {
            await _db.collection('usuarios').doc(user.uid).set({
              ...profileData,
              'uid': user.uid,
              'email': emailLower,
            }, SetOptions(merge: true));
          } catch (e) {
            debugPrint('Could not sync profile to UID doc: $e');
          }
        }
        return;
      }

      // No profile found — use minimal in-memory profile.
      _profile = _minimalProfile(user);
      _error = null;
      try {
        await _db.collection('usuarios').doc(user.uid).set({
          ..._profile!.toMap(),
          'uid': user.uid,
          'activo': true,
        }, SetOptions(merge: true));
      } catch (e) {
        debugPrint('Could not create placeholder profile: $e');
      }
    } catch (e) {
      debugPrint('Error resolving profile: $e');
      _profile = _minimalProfile(user);
      _error = null;
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
