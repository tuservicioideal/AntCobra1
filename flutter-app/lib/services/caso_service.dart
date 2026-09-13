import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';

import '../models/caso_model.dart';
import '../models/client_model.dart';
import '../utils/caso_problema.dart';
import '../utils/stream_memo.dart';

/// Servicio Firestore para el embudo de casos de problema.
class CasoService {
  final FirebaseFirestore _db;
  final _byEtapaMemo = StreamMemo<String, List<CasoModel>>();
  final _abiertosMemo = StreamMemo<int, List<CasoModel>>();
  final _allMemo = StreamMemo<int, List<CasoModel>>();
  final _comentariosMemo = StreamMemo<String, List<CasoComentario>>();
  final _movimientosMemo = StreamMemo<String, List<CasoMovimiento>>();

  CasoService({FirebaseFirestore? db}) : _db = db ?? FirebaseFirestore.instance;

  CollectionReference<Map<String, dynamic>> get _col =>
      _db.collection('casos');

  /// Abre o reabre un caso. Un solo caso abierto por (campaña, cliente, tipo).
  /// Si ya hay uno abierto: registra movimiento "Remarcado en campo".
  /// Si hay uno cerrado del mismo tipo: reabre a `nuevo`.
  Future<String> openOrReopenCaso({
    required String tipo,
    required String campaignId,
    required String section,
    required ClientModel client,
    String nota = '',
    double? lat,
    double? lng,
    String gestorUid = '',
    String gestorEmail = '',
    String gestorName = '',
  }) async {
    if (!isCasoTipo(tipo)) {
      throw ArgumentError('Tipo de caso inválido: $tipo');
    }

    final abiertoSnap = await _col
        .where('campaña_id', isEqualTo: campaignId)
        .where('cliente_id', isEqualTo: client.id)
        .where('tipo', isEqualTo: tipo)
        .where('abierto', isEqualTo: true)
        .limit(1)
        .get();

    if (abiertoSnap.docs.isNotEmpty) {
      final doc = abiertoSnap.docs.first;
      final batch = _db.batch();
      batch.update(doc.reference, {
        'nota_origen': nota,
        if (lat != null) 'gps_latitud': lat,
        if (lng != null) 'gps_longitud': lng,
        'gestor_uid': gestorUid,
        'gestor_nombre': gestorName,
        'gestor_email': gestorEmail,
        'actualizado_por_uid': gestorUid,
        'actualizado_por_nombre': gestorName,
        'fecha_etapa': FieldValue.serverTimestamp(),
      });
      batch.set(doc.reference.collection('movimientos').doc(), {
        'de': doc.data()['etapa']?.toString() ?? 'nuevo',
        'a': doc.data()['etapa']?.toString() ?? 'nuevo',
        'uid': gestorUid,
        'nombre': gestorName,
        'motivo': 'Remarcado en campo',
        'fecha': FieldValue.serverTimestamp(),
      });
      await batch.commit();
      return doc.id;
    }

    // Buscar cerrado del mismo tipo para reabrir (sin orderBy para evitar índice extra).
    final cerradoSnap = await _col
        .where('campaña_id', isEqualTo: campaignId)
        .where('cliente_id', isEqualTo: client.id)
        .where('tipo', isEqualTo: tipo)
        .where('abierto', isEqualTo: false)
        .limit(10)
        .get();

    if (cerradoSnap.docs.isNotEmpty) {
      final docs = [...cerradoSnap.docs];
      docs.sort((a, b) {
        final fa = a.data()['fecha_apertura'];
        final fb = b.data()['fecha_apertura'];
        final da = fa is Timestamp ? fa.toDate() : DateTime(1970);
        final db = fb is Timestamp ? fb.toDate() : DateTime(1970);
        return db.compareTo(da);
      });
      final doc = docs.first;
      final prevEtapa = doc.data()['etapa']?.toString() ?? 'resuelto';
      final batch = _db.batch();
      batch.update(doc.reference, {
        'etapa': 'nuevo',
        'abierto': true,
        'nota_origen': nota,
        if (lat != null) 'gps_latitud': lat,
        if (lng != null) 'gps_longitud': lng,
        'gestor_uid': gestorUid,
        'gestor_nombre': gestorName,
        'gestor_email': gestorEmail,
        'actualizado_por_uid': gestorUid,
        'actualizado_por_nombre': gestorName,
        'fecha_etapa': FieldValue.serverTimestamp(),
        'fecha_apertura': FieldValue.serverTimestamp(),
      });
      batch.set(doc.reference.collection('movimientos').doc(), {
        'de': prevEtapa,
        'a': 'nuevo',
        'uid': gestorUid,
        'nombre': gestorName,
        'motivo': 'Reabierto por remarcado en campo',
        'fecha': FieldValue.serverTimestamp(),
      });
      await batch.commit();
      return doc.id;
    }

    final ref = _col.doc();
    final batch = _db.batch();
    batch.set(ref, {
      'tipo': tipo,
      'etapa': 'nuevo',
      'abierto': true,
      'campaña_id': campaignId,
      'seccion': section,
      'seccion_key': client.seccionKey.isNotEmpty ? client.seccionKey : section,
      'cliente_id': client.id,
      'cliente_codigo': client.codigoCliente,
      'cliente_nombre': client.displayName,
      'cliente_dni': client.numeroDocumento,
      'telefono': client.telefonoMovil,
      'direccion': client.direccion,
      'distrito': client.distrito,
      'deuda_asignada': client.importeDeudaAsignada,
      'deuda_pendiente': client.importeDeudaPendiente,
      'campana_banco': client.campanaBanco,
      'nota_origen': nota,
      'gps_latitud': lat,
      'gps_longitud': lng,
      'gestor_uid': gestorUid,
      'gestor_nombre': gestorName,
      'gestor_email': gestorEmail,
      'fecha_apertura': FieldValue.serverTimestamp(),
      'fecha_etapa': FieldValue.serverTimestamp(),
      'actualizado_por_uid': gestorUid,
      'actualizado_por_nombre': gestorName,
    });
    batch.set(ref.collection('movimientos').doc(), {
      'de': '',
      'a': 'nuevo',
      'uid': gestorUid,
      'nombre': gestorName,
      'motivo': 'Apertura desde campo',
      'fecha': FieldValue.serverTimestamp(),
    });
    await batch.commit();
    return ref.id;
  }

  Future<void> moveEtapa({
    required String casoId,
    required String nuevaEtapa,
    required String uid,
    required String nombre,
    String motivo = '',
  }) async {
    if (!isCasoEtapa(nuevaEtapa)) {
      throw ArgumentError('Etapa inválida: $nuevaEtapa');
    }
    final ref = _col.doc(casoId);
    final snap = await ref.get();
    if (!snap.exists) {
      throw StateError('Caso no encontrado: $casoId');
    }
    final data = snap.data() ?? {};
    final prev = data['etapa']?.toString() ?? 'nuevo';
    if (prev == nuevaEtapa) return;
    if (!canMoveCasoEtapa(prev, nuevaEtapa)) {
      throw StateError('Transición no permitida: $prev → $nuevaEtapa');
    }

    final batch = _db.batch();
    batch.update(ref, {
      'etapa': nuevaEtapa,
      'abierto': isEtapaAbierta(nuevaEtapa),
      'fecha_etapa': FieldValue.serverTimestamp(),
      'actualizado_por_uid': uid,
      'actualizado_por_nombre': nombre,
    });
    batch.set(ref.collection('movimientos').doc(), {
      'de': prev,
      'a': nuevaEtapa,
      'uid': uid,
      'nombre': nombre,
      'motivo': motivo,
      'fecha': FieldValue.serverTimestamp(),
    });
    await batch.commit();
  }

  Future<void> addComentario({
    required String casoId,
    required String texto,
    required String uid,
    required String nombre,
  }) async {
    final trimmed = texto.trim();
    if (trimmed.isEmpty) return;
    await _col.doc(casoId).collection('comentarios').add({
      'texto': trimmed,
      'uid': uid,
      'nombre': nombre,
      'fecha': FieldValue.serverTimestamp(),
    });
  }

  Stream<List<CasoModel>> streamByEtapa(String etapa, {int limit = 100}) {
    return _byEtapaMemo.remember('$etapa:$limit', () {
      return _col
          .where('etapa', isEqualTo: etapa)
          .orderBy('fecha_apertura', descending: true)
          .limit(limit)
          .snapshots()
          .map((snap) => snap.docs
              .map((d) => CasoModel.fromMap(d.id, d.data()))
              .toList());
    });
  }

  Stream<List<CasoModel>> streamAbiertos({int limit = 300}) {
    return _abiertosMemo.remember(limit, () {
      return _col
          .where('abierto', isEqualTo: true)
          .orderBy('fecha_apertura', descending: true)
          .limit(limit)
          .snapshots()
          .map((snap) => snap.docs
              .map((d) => CasoModel.fromMap(d.id, d.data()))
              .toList());
    });
  }

  Stream<List<CasoModel>> streamAll({int limit = 500}) {
    return _allMemo.remember(limit, () {
      return _col
          .orderBy('fecha_apertura', descending: true)
          .limit(limit)
          .snapshots()
          .map((snap) => snap.docs
              .map((d) => CasoModel.fromMap(d.id, d.data()))
              .toList());
    });
  }

  Future<CasoModel?> getCaso(String casoId) async {
    final snap = await _col.doc(casoId).get();
    if (!snap.exists) return null;
    return CasoModel.fromMap(snap.id, snap.data() ?? {});
  }

  Stream<List<CasoComentario>> streamComentarios(String casoId) {
    return _comentariosMemo.remember(casoId, () {
      return _col
          .doc(casoId)
          .collection('comentarios')
          .orderBy('fecha', descending: false)
          .snapshots()
          .map((snap) => snap.docs
              .map((d) => CasoComentario.fromMap(d.id, d.data()))
              .toList());
    });
  }

  Stream<List<CasoMovimiento>> streamMovimientos(String casoId) {
    return _movimientosMemo.remember(casoId, () {
      return _col
          .doc(casoId)
          .collection('movimientos')
          .orderBy('fecha', descending: true)
          .snapshots()
          .map((snap) => snap.docs
              .map((d) => CasoMovimiento.fromMap(d.id, d.data()))
              .toList());
    });
  }

  /// Pure helper for tests: decide action given existing cases.
  @visibleForTesting
  static String resolveOpenAction({
    required bool hasOpen,
    required bool hasClosed,
  }) {
    if (hasOpen) return 'remark';
    if (hasClosed) return 'reopen';
    return 'create';
  }
}
