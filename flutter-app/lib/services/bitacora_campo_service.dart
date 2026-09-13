import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';

import '../models/bitacora_campo_entry.dart';

/// Índice denormalizado `bitacora_campo` para consulta admin/supervisor.
class BitacoraCampoService {
  BitacoraCampoService({FirebaseFirestore? db}) : _db = db ?? FirebaseFirestore.instance;

  final FirebaseFirestore _db;

  CollectionReference<Map<String, dynamic>> get _col =>
      _db.collection('bitacora_campo');

  static String formatFechaDia(DateTime dt) {
    final y = dt.year;
    final m = dt.month.toString().padLeft(2, '0');
    final d = dt.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  /// Mapa listo para WriteBatch / set.
  static Map<String, dynamic> buildEventMap({
    required String tipo,
    required DateTime when,
    required String campaignId,
    required String seccionKey,
    required String clienteId,
    required String clienteNombre,
    required String codigoCliente,
    required String dni,
    required String usuarioUid,
    required String usuarioNombre,
    required String usuarioRol,
    required String resumen,
    required String origenId,
    required String origenColeccion,
    required Map<String, dynamic> payload,
    FieldValue? creadoAtServer,
  }) {
    return {
      'tipo': tipo,
      'creado_at': creadoAtServer ?? Timestamp.fromDate(when),
      'fecha_dia': formatFechaDia(when),
      'campaign_id': campaignId,
      'seccion_key': seccionKey,
      'cliente_id': clienteId,
      'cliente_nombre': clienteNombre,
      'codigo_cliente': codigoCliente,
      'dni': dni,
      'usuario_uid': usuarioUid,
      'usuario_nombre': usuarioNombre,
      'usuario_rol': usuarioRol,
      'resumen': resumen,
      'origen_id': origenId,
      'origen_coleccion': origenColeccion,
      'payload': payload,
    };
  }

  DocumentReference<Map<String, dynamic>> docRef(String eventId) =>
      _col.doc(eventId);

  /// Escritura suelta (fail-open). Preferir WriteBatch desde FirestoreService.
  Future<void> registrar({
    required String eventId,
    required Map<String, dynamic> data,
  }) async {
    try {
      await _col.doc(eventId).set(data, SetOptions(merge: false));
    } catch (e) {
      debugPrint('BitacoraCampoService.registrar falló ($eventId): $e');
    }
  }

  Future<List<BitacoraCampoEntry>> queryFeed({
    required DateTime day,
    String? tipo,
    String? dni,
    String? seccionKey,
    String? usuarioUid,
    String? campaignId,
    int limit = 200,
  }) async {
    final fechaDia = formatFechaDia(day);
    Query<Map<String, dynamic>> q = _col;

    if (dni != null && dni.trim().isNotEmpty) {
      q = q
          .where('dni', isEqualTo: dni.trim())
          .orderBy('creado_at', descending: true)
          .limit(limit);
    } else if (usuarioUid != null && usuarioUid.isNotEmpty) {
      q = q
          .where('usuario_uid', isEqualTo: usuarioUid)
          .orderBy('creado_at', descending: true)
          .limit(limit);
    } else if (seccionKey != null && seccionKey.isNotEmpty) {
      q = q
          .where('seccion_key', isEqualTo: seccionKey)
          .orderBy('creado_at', descending: true)
          .limit(limit);
    } else if (campaignId != null &&
        campaignId.isNotEmpty &&
        tipo != null &&
        tipo.isNotEmpty &&
        tipo != 'todos' &&
        tipo != 'notas') {
      q = q
          .where('campaign_id', isEqualTo: campaignId)
          .where('tipo', isEqualTo: tipo)
          .orderBy('creado_at', descending: true)
          .limit(limit);
    } else if (tipo != null &&
        tipo.isNotEmpty &&
        tipo != 'todos' &&
        tipo != 'notas') {
      q = q
          .where('tipo', isEqualTo: tipo)
          .where('fecha_dia', isEqualTo: fechaDia)
          .orderBy('creado_at', descending: true)
          .limit(limit);
    } else {
      q = q
          .where('fecha_dia', isEqualTo: fechaDia)
          .orderBy('creado_at', descending: true)
          .limit(limit);
    }

    try {
      final snap = await q.get();
      var entries = snap.docs
          .map((d) => BitacoraCampoEntry.fromMap(d.id, d.data()))
          .toList();

      if (dni == null || dni.trim().isEmpty) {
        entries = entries.where((e) => e.fechaDia == fechaDia).toList();
      }
      if (tipo == 'notas') {
        entries = entries.where((e) => e.isNota).toList();
      } else if (tipo != null &&
          tipo.isNotEmpty &&
          tipo != 'todos' &&
          ((dni != null && dni.trim().isNotEmpty) ||
              (usuarioUid != null && usuarioUid.isNotEmpty) ||
              (seccionKey != null && seccionKey.isNotEmpty))) {
        entries = entries.where((e) => e.tipo == tipo).toList();
      }
      if (seccionKey != null &&
          seccionKey.isNotEmpty &&
          dni != null &&
          dni.trim().isNotEmpty) {
        entries = entries.where((e) => e.seccionKey == seccionKey).toList();
      }
      if (usuarioUid != null &&
          usuarioUid.isNotEmpty &&
          ((dni != null && dni.trim().isNotEmpty) ||
              (seccionKey != null && seccionKey.isNotEmpty))) {
        entries = entries.where((e) => e.usuarioUid == usuarioUid).toList();
      }
      if (campaignId != null && campaignId.isNotEmpty) {
        entries = entries.where((e) => e.campaignId == campaignId).toList();
      }

      entries.sort((a, b) => b.sortKey.compareTo(a.sortKey));
      return entries;
    } catch (e) {
      debugPrint('BitacoraCampoService.queryFeed: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>?> getDoxeoJob(String jobId) async {
    if (jobId.isEmpty) return null;
    try {
      final snap = await _db.collection('doxeo_jobs').doc(jobId).get();
      if (!snap.exists || snap.data() == null) return null;
      return {'id': snap.id, ...snap.data()!};
    } catch (e) {
      debugPrint('BitacoraCampoService.getDoxeoJob: $e');
      return null;
    }
  }
}
