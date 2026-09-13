import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/foundation.dart';

import '../models/cartera_job_model.dart';
import '../utils/stream_memo.dart';

class CarteraUploadService {
  CarteraUploadService({
    FirebaseFirestore? firestore,
    FirebaseStorage? storage,
    FirebaseFunctions? functions,
    FirebaseAuth? auth,
  })  : _db = firestore ?? FirebaseFirestore.instance,
        _storage = storage ?? FirebaseStorage.instance,
        _functions = functions ??
            FirebaseFunctions.instanceFor(region: 'us-central1'),
        _auth = auth ?? FirebaseAuth.instance;

  final FirebaseFirestore _db;
  final FirebaseStorage _storage;
  final FirebaseFunctions _functions;
  final FirebaseAuth _auth;
  final _jobMemo = StreamMemo<String, CarteraJob>();

  String get _uid {
    final uid = _auth.currentUser?.uid ?? '';
    if (uid.isEmpty) {
      throw Exception('Debes iniciar sesión.');
    }
    return uid;
  }

  CollectionReference<Map<String, dynamic>> get _jobs =>
      _db.collection('trabajos_cartera');

  Stream<CarteraJob> watchJob(String jobId) {
    return _jobMemo.remember(jobId, () {
      return _jobs.doc(jobId).snapshots().map((snap) {
        final data = snap.data() ?? <String, dynamic>{};
        return CarteraJob.fromMap(snap.id, data);
      });
    });
  }

  Future<String> uploadAndCreateJob({
    required Uint8List bytes,
    required String filename,
    String campaignId = 'cartera_activa',
  }) async {
    final uid = _uid;
    final jobRef = _jobs.doc();
    final jobId = jobRef.id;
    final storagePath = 'cartera_uploads/$uid/$jobId/origen.xlsx';
    final profile = await _db.collection('usuarios').doc(uid).get();
    final nombre = profile.data()?['nombre']?.toString() ?? '';

    await _storage.ref(storagePath).putData(
          bytes,
          SettableMetadata(
            contentType:
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          ),
        );

    await jobRef.set({
      'estado': 'subiendo',
      'campaign_id': campaignId,
      'creado_por_uid': uid,
      'creado_por_nombre': nombre,
      'creado_at': FieldValue.serverTimestamp(),
      'archivo': {
        'storage_path': storagePath,
        'nombre': filename,
        'bytes': bytes.length,
      },
    });
    return jobId;
  }

  Future<List<CarteraJob>> listRecentJobs({int limit = 20}) async {
    final uid = _uid;
    final snap = await _jobs
        .where('creado_por_uid', isEqualTo: uid)
        .orderBy('creado_at', descending: true)
        .limit(limit)
        .get();
    return snap.docs.map((d) => CarteraJob.fromMap(d.id, d.data())).toList();
  }

  Future<void> parseJob(String jobId) async {
    final callable = _functions.httpsCallable(
      'parseCarteraExcel',
      options: HttpsCallableOptions(timeout: const Duration(minutes: 9)),
    );
    await callable.call<Map<String, dynamic>>({'jobId': jobId});
  }

  Future<void> publishJob(String jobId) async {
    final callable = _functions.httpsCallable(
      'publishCarteraExcel',
      options: HttpsCallableOptions(timeout: const Duration(minutes: 30)),
    );
    await callable.call<Map<String, dynamic>>({
      'jobId': jobId,
      'confirmar': true,
    });
  }

  String mapError(Object error) {
    final message = error.toString();
    if (message.contains('permission-denied') ||
        message.contains('PERMISSION_DENIED')) {
      return 'No tienes permiso para cargar cartera.';
    }
    if (message.contains('unauthenticated') ||
        message.contains('UNAUTHENTICATED')) {
      return 'Debes iniciar sesión.';
    }
    if (message.contains('excel_invalido') ||
        message.contains('invalid-argument') ||
        message.contains('INVALID_ARGUMENT')) {
      return _extractCallableMessage(message) ??
          'El Excel no tiene el formato del banco.';
    }
    if (message.contains('aborted') || message.contains('ABORTED')) {
      return 'Hay otra publicación en curso. Espera a que termine.';
    }
    if (message.contains('deadline-exceeded') ||
        message.contains('TimeoutException')) {
      return 'La operación tardó demasiado. Revisa el estado del trabajo e intenta de nuevo.';
    }
    debugPrint('CarteraUploadService error: $error');
    return 'No se pudo completar la carga. Intenta de nuevo.';
  }

  String? _extractCallableMessage(String message) {
    final match = RegExp(r'message:\s*(.+?)(?:,|\])').firstMatch(message);
    return match?.group(1)?.trim();
  }
}
