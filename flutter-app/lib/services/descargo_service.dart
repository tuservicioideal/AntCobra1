import 'dart:io';
import 'dart:typed_data';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;

import '../models/descargo_model.dart';

/// Evidencia local pendiente de subir (foto tomada o audio grabado).
///
/// En web (`kIsWeb`) no hay rutas de archivo (`dart:io` no existe y
/// `FilePicker.path` siempre es null), así que se guardan los [bytes] en
/// memoria y se suben con `putData`. En móvil se usa [localPath] con `putFile`.
class PendingEvidencia {
  final String tipo; // 'foto' | 'audio'
  final String localPath;
  final String mimeType;
  final Uint8List? bytes;
  final String fileName;

  const PendingEvidencia({
    required this.tipo,
    required this.localPath,
    required this.mimeType,
    this.bytes,
    this.fileName = '',
  });

  /// Nombre para mostrar en la UI (funciona en web y móvil).
  String get displayName {
    if (fileName.isNotEmpty) return fileName;
    if (localPath.isEmpty) return tipo == 'audio' ? 'audio' : 'foto';
    final parts = localPath.split(RegExp(r'[/\\]'));
    return parts.isNotEmpty ? parts.last : localPath;
  }
}

/// CRUD de descargos + subida de fotos/audios a Storage.
///
/// Firestore:
///   campañas/{campaignId}/gestores/{section}/clientes/{clientId}/descargos/{id}
/// Storage:
///   descargos_evidencias/{campaignId}/{section}/{clientId}/{descargoId}_{i}.{ext}
class DescargoService {
  DescargoService({
    FirebaseFirestore? firestore,
    FirebaseStorage? storage,
    FirebaseAuth? auth,
  })  : _db = firestore ?? FirebaseFirestore.instance,
        _storage = storage ?? FirebaseStorage.instance,
        _auth = auth ?? FirebaseAuth.instance;

  final FirebaseFirestore _db;
  final FirebaseStorage _storage;
  final FirebaseAuth _auth;

  static const int maxFotos = 3;
  static const int maxAudios = 2;
  static const int maxFotoBytes = 5 * 1024 * 1024;
  static const int maxAudioBytes = 10 * 1024 * 1024;

  CollectionReference<Map<String, dynamic>> _col(
    String campaignId,
    String section,
    String clientId,
  ) {
    return _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId)
        .collection('descargos');
  }

  /// Lista en tiempo real (últimos 20, más recientes primero).
  ///
  /// Nota: no se traga el error con `handleError → []` porque eso hacía que
  /// la UI mostrara "Sin descargos" aunque el guardado sí funcionó.
  /// El `StreamBuilder` debe revisar `snapshot.hasError`.
  Stream<List<DescargoModel>> streamDescargos({
    required String campaignId,
    required String section,
    required String clientId,
  }) {
    return _col(campaignId, section, clientId)
        .orderBy('fecha', descending: true)
        .limit(20)
        .snapshots()
        .map((snap) =>
            snap.docs.map((d) => DescargoModel.fromMap(d.id, d.data())).toList());
  }

  Future<List<DescargoModel>> getDescargos({
    required String campaignId,
    required String section,
    required String clientId,
    int limit = 20,
  }) async {
    try {
      final snap = await _col(campaignId, section, clientId)
          .orderBy('fecha', descending: true)
          .limit(limit)
          .get();
      return snap.docs.map((d) => DescargoModel.fromMap(d.id, d.data())).toList();
    } catch (e) {
      debugPrint('getDescargos: $e');
      return [];
    }
  }

  String _extFor(String tipo, String mime, String localPath, {String fileName = ''}) {
    final source = localPath.isNotEmpty ? localPath : fileName;
    final fromPath = source.split('.').last.toLowerCase();
    if (fromPath.length <= 5 && !fromPath.contains('/') && !fromPath.contains('\\') && source.contains('.')) return fromPath;
    if (tipo == 'audio') {
      if (mime.contains('mp4') || mime.contains('aac')) return 'm4a';
      if (mime.contains('wav')) return 'wav';
      return 'm4a';
    }
    if (mime.contains('png')) return 'png';
    if (mime.contains('webp')) return 'webp';
    return 'jpg';
  }

  Future<DescargoEvidencia> _uploadOne({
    required String campaignId,
    required String section,
    required String clientId,
    required String descargoId,
    required int index,
    required PendingEvidencia pending,
  }) async {
    final ext = _extFor(pending.tipo, pending.mimeType, pending.localPath,
        fileName: pending.fileName);
    final fileName = '${descargoId}_$index.$ext';
    final storagePath =
        'descargos_evidencias/$campaignId/$section/$clientId/$fileName';
    final ref = _storage.ref(storagePath);

    final mime = pending.mimeType.isNotEmpty
        ? pending.mimeType
        : (pending.tipo == 'audio' ? 'audio/m4a' : 'image/jpeg');

    try {
      // Web o bytes en memoria → putData (en web no existe dart:io File
      // y FilePicker.path siempre es null).
      if (pending.bytes != null) {
        await ref.putData(pending.bytes!, SettableMetadata(contentType: mime));
        final url = await ref.getDownloadURL();
        return DescargoEvidencia(
          tipo: pending.tipo,
          storagePath: storagePath,
          downloadUrl: url,
          mimeType: mime,
          sizeBytes: pending.bytes!.length,
        );
      }
      if (kIsWeb) {
        throw StateError(
            'No se pudo leer el archivo en web. Vuelve a adjuntarlo.');
      }
      final file = File(pending.localPath);
      final size = await file.length();
      await ref.putFile(file, SettableMetadata(contentType: mime));
      final url = await ref.getDownloadURL();
      return DescargoEvidencia(
        tipo: pending.tipo,
        storagePath: storagePath,
        downloadUrl: url,
        mimeType: mime,
        sizeBytes: size,
      );
    } on FirebaseException catch (e) {
      throw StateError(_friendlyStorageError(e));
    }
  }

  String _friendlyStorageError(FirebaseException e) {
    final code = e.code.toLowerCase();
    if (code.contains('unauthorized') || code.contains('permission-denied')) {
      return 'Sin permiso para subir evidencias. Revisa tu sesión y que tengas la sección asignada.';
    }
    if (code.contains('unauthenticated')) {
      return 'Sesión vencida. Vuelve a iniciar sesión e intenta de nuevo.';
    }
    if (code.contains('canceled') || code.contains('cancelled')) {
      return 'Subida cancelada. Intenta de nuevo.';
    }
    if (code.contains('retry') ||
        code.contains('unavailable') ||
        code.contains('network') ||
        code.contains('timeout')) {
      return 'Sin conexión para subir foto/audio. Revisa internet e intenta de nuevo.';
    }
    if (code.contains('quota') || code.contains('exceeded')) {
      return 'Almacenamiento lleno. Avisa al administrador.';
    }
    return 'No se pudo subir la evidencia (${e.code}). Revisa internet e intenta de nuevo.';
  }

  String _friendlyFirestoreError(Object e) {
    final s = e.toString().toLowerCase();
    if (s.contains('permission-denied') || s.contains('permission denied')) {
      return 'Sin permiso para registrar el descargo. Revisa tu sesión y que tengas la sección asignada.';
    }
    if (s.contains('unavailable') || s.contains('network') || s.contains('timeout')) {
      return 'Sin conexión para guardar el descargo. Revisa internet e intenta de nuevo.';
    }
    return 'No se pudo guardar el descargo. Revisa internet e intenta de nuevo.';
  }

  /// Crea el descargo: sube evidencias y guarda el documento.
  /// Lanza [StateError] con mensaje amigable si algo falla.
  Future<String> addDescargo({
    required String campaignId,
    required String section,
    required String clientId,
    required String tipoRespuesta,
    required String texto,
    List<PendingEvidencia> evidencias = const [],
    double? lat,
    double? lng,
    String gestorUid = '',
    String gestorNombre = '',
  }) async {
    if (campaignId.isEmpty || section.isEmpty || clientId.isEmpty) {
      throw StateError('Falta campaña, sección o cliente. Vuelve a abrir la ficha.');
    }
    final clean = texto.trim();
    if (clean.length < 10) {
      throw StateError(
          'El descargo debe tener al menos 10 caracteres. Describe con tus palabras lo que respondió (${clean.length}/10).');
    }
    final fotos = evidencias.where((e) => e.tipo != 'audio').toList();
    final audios = evidencias.where((e) => e.tipo == 'audio').toList();
    if (fotos.length > maxFotos) {
      throw StateError('Máximo $maxFotos fotos por descargo.');
    }
    if (audios.length > maxAudios) {
      throw StateError('Máximo $maxAudios audios por descargo.');
    }
    final uid = gestorUid.isNotEmpty
        ? gestorUid
        : (_auth.currentUser?.uid ?? '');
    if (uid.isEmpty) throw StateError('Sin sesión activa. Vuelve a iniciar sesión.');

    final docRef = _col(campaignId, section, clientId).doc();
    final uploaded = <DescargoEvidencia>[];
    var i = 0;
    for (final p in evidencias) {
      final int size;
      if (p.bytes != null) {
        size = p.bytes!.length;
      } else {
        if (kIsWeb) {
          throw StateError(
              'No se pudo leer un archivo adjunto en web. Quítalo y vuelve a adjuntarlo.');
        }
        final f = File(p.localPath);
        if (!f.existsSync()) continue;
        size = await f.length();
      }
      if (p.tipo == 'audio' && size > maxAudioBytes) {
        throw StateError('Un audio supera 10 MB. Graba uno más corto.');
      }
      if (p.tipo != 'audio' && size > maxFotoBytes) {
        throw StateError('Una foto supera 5 MB. Toma otra con menor calidad.');
      }
      uploaded.add(await _uploadOne(
        campaignId: campaignId,
        section: section,
        clientId: clientId,
        descargoId: docRef.id,
        index: i++,
        pending: p,
      ));
    }

    final now = DateTime.now();
    try {
      await docRef.set({
        'tipo_respuesta': tipoRespuesta,
        'texto': clean,
        'gestor_uid': uid,
        'gestor_nombre': gestorNombre,
        // Timestamp para que orderBy('fecha') sea consistente.
        // fromMap sigue aceptando los docs antiguos guardados como string ISO.
        'fecha': Timestamp.now(),
        'fecha_iso': now.toIso8601String(),
        'created_at': FieldValue.serverTimestamp(),
        'gps_latitud': lat ?? 0,
        'gps_longitud': lng ?? 0,
        'seccion_key': section,
        'campaign_id': campaignId,
        'client_id': clientId,
        'evidencias': uploaded.map((e) => e.toMap()).toList(),
      });
    } catch (e) {
      if (e is StateError) rethrow;
      debugPrint('addDescargo set: $e');
      throw StateError(_friendlyFirestoreError(e));
    }
    return docRef.id;
  }

  Future<void> deleteDescargo({
    required String campaignId,
    required String section,
    required String clientId,
    required String descargoId,
  }) async {
    // Nota: no borramos los archivos de Storage para mantener auditoría.
    await _col(campaignId, section, clientId).doc(descargoId).delete();
  }
}
