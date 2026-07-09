import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../models/client_model.dart';
import '../models/visita_historial.dart';
import '../models/my_routes_load_result.dart';
import '../models/tracking_models.dart';
import '../models/user_model.dart';
import '../utils/section_utils.dart';
import 'campaign_service.dart';
import 'notification_service.dart';

/// Core Firestore operations for clients and users.
class FirestoreService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  // ─────────────────── CLIENTS ───────────────────

  String _dedupKey(ClientModel c) =>
      c.numeroDocumento.isNotEmpty ? c.numeroDocumento : c.codigoCliente;

  List<ClientModel> _dedupeClientsWithCounts(List<ClientModel> allClients) {
    final counts = <String, int>{};
    for (final c in allClients) {
      final key = _dedupKey(c);
      counts[key] = (counts[key] ?? 0) + 1;
    }
    final deduped = <String, ClientModel>{};
    for (final c in allClients) {
      final key = _dedupKey(c);
      final existing = deduped[key];
      if (existing == null || !c.isPendiente) {
        deduped[key] = c.copyWith(cuentasMismoDni: counts[key] ?? 1);
      }
    }
    return deduped.values.toList();
  }

  /// Load all clients for a given campaign + section (single composite key).
  Future<List<ClientModel>> getClients(String campaignId, String section) async {
    try {
      final snapshot = await _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(section)
          .collection('clientes')
          .get();

      return snapshot.docs.map((doc) {
        final data = Map<String, dynamic>.from(doc.data());
        // Garantiza seccion_key = path Firestore (crítico para reasignación).
        if ((data['seccion_key']?.toString() ?? '').isEmpty) {
          data['seccion_key'] = section;
        }
        return ClientModel.fromMap(doc.id, data, campaignId: campaignId);
      }).toList();
    } catch (e) {
      debugPrint('Error loading clients: $e');
      return [];
    }
  }

  /// Load only clients with coordinates for a specific section.
  /// Optional limit prevents expensive reads when sections are large.
  Future<List<ClientModel>> getClientsWithCoordinates(
    String campaignId,
    String section, {
    int limit = 250,
  }) async {
    try {
      Query<Map<String, dynamic>> query = _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(section)
          .collection('clientes');
      if (limit > 0) {
        query = query.limit(limit);
      }

      final snapshot = await query.get().timeout(const Duration(seconds: 20));
      return snapshot.docs
          .map((doc) {
            final data = Map<String, dynamic>.from(doc.data());
            if ((data['seccion_key']?.toString() ?? '').isEmpty) {
              data['seccion_key'] = section;
            }
            return ClientModel.fromMap(doc.id, data, campaignId: campaignId);
          })
          .where((c) => c.hasCoordinates)
          .toList();
    } catch (e) {
      debugPrint('Error loading clients with coordinates: $e');
      rethrow;
    }
  }

  /// Clientes geolocalizados de varias secciones (deduplicados por DNI/código).
  Future<List<ClientModel>> getClientsWithCoordinatesMultiSection(
    String campaignId,
    List<String> sectionKeys, {
    int limitPerSection = 250,
  }) async {
    if (sectionKeys.isEmpty) return [];

    final deduped = <String, ClientModel>{};

    Future<void> loadSection(String section) async {
      try {
        final clients = await getClientsWithCoordinates(
          campaignId,
          section,
          limit: limitPerSection,
        );
        for (final c in clients) {
          final key = c.numeroDocumento.isNotEmpty ? c.numeroDocumento : c.id;
          deduped[key] = c;
        }
      } catch (e) {
        debugPrint('Error loading section $section for map: $e');
      }
    }

    await Future.wait(sectionKeys.map(loadSection))
        .timeout(const Duration(seconds: 25));

    return deduped.values.toList();
  }

  /// Load clients from multiple section keys and merge (deduplicating by DNI).
  Future<List<ClientModel>> getClientsMultiSection(
      String campaignId, List<String> sectionKeys) async {
    final all = <ClientModel>[];
    for (final key in sectionKeys) {
      all.addAll(await getClients(campaignId, key));
    }
    return _dedupeClientsWithCounts(all);
  }

  // ─────────────────── RUTAS DIARIAS ───────────────────

  /// Carga la ruta del gestor actual para una fecha específica (YYYY-MM-DD).
  Future<Map<String, dynamic>?> getMyRouteByDate(String fecha) async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null || uid.isEmpty) return null;

      final docId = '${fecha}_$uid';
      final snap = await _db
          .collection('rutas_diarias')
          .doc(docId)
          .get()
          .timeout(const Duration(seconds: 20));
      if (!snap.exists || snap.data() == null) return null;
      return {'id': snap.id, ...snap.data()!};
    } catch (e) {
      debugPrint('Error loading my route by date: $e');
      return null;
    }
  }

  /// Lista rutas del gestor actual por fecha descendente.
  Future<MyRoutesLoadResult> getMyRoutes({int limit = 30}) async {
    final uid = _auth.currentUser?.uid;
    if (uid == null || uid.isEmpty) {
      return const MyRoutesLoadResult(
        routes: [],
        error: 'Sesión no válida. Vuelve a iniciar sesión.',
      );
    }

    try {
      final routes = await _queryMyRoutesOrdered(uid, limit);
      return MyRoutesLoadResult(routes: routes);
    } on FirebaseException catch (e) {
      if (_isMissingIndexError(e)) {
        debugPrint('getMyRoutes: índice compuesto pendiente, usando fallback: $e');
        try {
          final routes = await _queryMyRoutesFallback(uid, limit);
          return MyRoutesLoadResult(
            routes: routes,
            warning: routes.isEmpty
                ? null
                : 'Listado en modo alternativo. Si falta alguna ruta, espera unos minutos y actualiza.',
          );
        } catch (fallbackError) {
          debugPrint('getMyRoutes fallback failed: $fallbackError');
          return MyRoutesLoadResult(
            routes: [],
            error: _friendlyRoutesError(fallbackError),
          );
        }
      }
      debugPrint('Error loading my routes: $e');
      return MyRoutesLoadResult(routes: [], error: _friendlyRoutesError(e));
    } catch (e) {
      debugPrint('Error loading my routes: $e');
      return MyRoutesLoadResult(routes: [], error: _friendlyRoutesError(e));
    }
  }

  Future<List<Map<String, dynamic>>> _queryMyRoutesOrdered(String uid, int limit) async {
    Query<Map<String, dynamic>> query = _db
        .collection('rutas_diarias')
        .where('gestor_uid', isEqualTo: uid)
        .orderBy('fecha', descending: true);

    if (limit > 0) {
      query = query.limit(limit);
    }

    final snap = await query.get().timeout(const Duration(seconds: 20));
    return snap.docs.map((d) => {'id': d.id, ...d.data()}).toList();
  }

  Future<List<Map<String, dynamic>>> _queryMyRoutesFallback(String uid, int limit) async {
    Query<Map<String, dynamic>> query = _db
        .collection('rutas_diarias')
        .where('gestor_uid', isEqualTo: uid);

    if (limit > 0) {
      query = query.limit(limit);
    }

    final snap = await query.get().timeout(const Duration(seconds: 20));
    final routes = snap.docs.map((d) => {'id': d.id, ...d.data()}).toList();
    routes.sort((a, b) {
      final fa = a['fecha']?.toString() ?? '';
      final fb = b['fecha']?.toString() ?? '';
      return fb.compareTo(fa);
    });
    return routes;
  }

  bool _isMissingIndexError(FirebaseException e) {
    final code = e.code.toLowerCase();
    final message = (e.message ?? '').toLowerCase();
    return code == 'failed-precondition' &&
        (message.contains('index') || message.contains('índice'));
  }

  String _friendlyRoutesError(Object e) {
    final text = e.toString().toLowerCase();
    if (text.contains('permission-denied') || text.contains('permission denied')) {
      return 'No tienes permiso para ver tus rutas. Contacta al administrador.';
    }
    if (text.contains('unavailable') || text.contains('network')) {
      return 'Sin conexión. Revisa tu red e intenta de nuevo.';
    }
    if (text.contains('failed-precondition') && text.contains('index')) {
      return 'El servidor está preparando el índice de rutas. Intenta en unos minutos.';
    }
    return 'No se pudieron cargar tus rutas. Desliza hacia abajo para reintentar.';
  }

  /// Guarda/actualiza la ruta diaria del gestor autenticado.
  Future<String?> saveMyRoute({
    required String fecha,
    required String gestorNombre,
    required List<ClientModel> clientes,
  }) async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null || uid.isEmpty) return null;

      final docId = '${fecha}_$uid';
      final now = DateTime.now().toIso8601String();
      final payloadClients = clientes
          .map((c) => {
                'codigo_cliente': c.id,
                'nombre': c.displayName,
                'seccion_key': c.seccionKey,
                'lat': c.latitude == 0 ? null : c.latitude,
                'lng': c.longitude == 0 ? null : c.longitude,
                'estado': c.estadoGestion,
                'importe_deuda': c.importeDeudaAsignada,
              })
          .toList();
      final completados =
          payloadClients.where((c) => (c['estado']?.toString() ?? 'pendiente') != 'pendiente').length;

      await _db.collection('rutas_diarias').doc(docId).set({
        'gestor_uid': uid,
        'gestor_nombre': gestorNombre,
        'fecha': fecha,
        'clientes': payloadClients,
        'total': payloadClients.length,
        'completados': completados,
        'created_at': now,
        'updated_at': now,
      }, SetOptions(merge: true));

      return docId;
    } catch (e) {
      debugPrint('Error saving my route: $e');
      return null;
    }
  }

  /// Actualiza el nombre personalizado de una ruta del gestor actual.
  Future<bool> updateMyRouteName({
    required String docId,
    String? nombre,
  }) async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null || uid.isEmpty) return false;
      if (!docId.endsWith('_$uid')) return false;

      final update = <String, dynamic>{
        'updated_at': DateTime.now().toIso8601String(),
      };
      final trimmed = nombre?.trim() ?? '';
      if (trimmed.isEmpty) {
        update['nombre'] = FieldValue.delete();
      } else {
        update['nombre'] = trimmed;
      }

      await _db.collection('rutas_diarias').doc(docId).update(update);
      return true;
    } catch (e) {
      debugPrint('Error updating route name: $e');
      return false;
    }
  }

  /// Elimina una ruta del gestor actual.
  Future<bool> deleteMyRoute(String docId) async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null || uid.isEmpty) return false;
      if (!docId.endsWith('_$uid')) return false;

      await _db.collection('rutas_diarias').doc(docId).delete();
      return true;
    } catch (e) {
      debugPrint('Error deleting route: $e');
      return false;
    }
  }

  /// Stream real-time client updates.
  Stream<List<ClientModel>> streamClients(String campaignId, String section) {
    return _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .snapshots()
        .map((snap) => snap.docs.map((doc) {
              final data = Map<String, dynamic>.from(doc.data());
              if ((data['seccion_key']?.toString() ?? '').isEmpty) {
                data['seccion_key'] = section;
              }
              return ClientModel.fromMap(doc.id, data, campaignId: campaignId);
            }).toList());
  }

  /// Stream merged clients from multiple sections (dedup by DNI).
  Stream<List<ClientModel>> streamClientsMultiSection(
      String campaignId, List<String> sectionKeys) {
    if (sectionKeys.isEmpty) return Stream.value([]);
    if (sectionKeys.length == 1) {
      return streamClients(campaignId, sectionKeys.first)
          .map(_dedupeClientsWithCounts);
    }

    final controller = StreamController<List<ClientModel>>();
    final latest = <String, List<ClientModel>>{};
    final subs = <StreamSubscription<List<ClientModel>>>[];

    void emitMerged() {
      final all = <ClientModel>[];
      for (final list in latest.values) {
        all.addAll(list);
      }
      if (!controller.isClosed) {
        controller.add(_dedupeClientsWithCounts(all));
      }
    }

    for (final key in sectionKeys) {
      subs.add(streamClients(campaignId, key).listen(
        (clients) {
          latest[key] = clients;
          emitMerged();
        },
        onError: controller.addError,
      ));
    }

    controller.onCancel = () async {
      for (final s in subs) {
        await s.cancel();
      }
    };

    return controller.stream;
  }

  /// Update a client's gestion status with GPS, notes, and nivel fields.
  Future<void> updateClientStatus({
    required String campaignId,
    required String section,
    required String clientId,
    required String estado,
    String nota = '',
    double? lat,
    double? lng,
    String? nivel1,
    String? nivel2,
    String? nivel3,
    String? nivel4,
    String? canalGestion,
    String? fechaPromesaPago,
    double? montoPromesaPago,
    List<Map<String, dynamic>>? cartasGestor,
    String? gestorUid,
    String? gestorNombre,
  }) async {
    final now = DateTime.now().toIso8601String();
    final data = <String, dynamic>{
      'estado_gestion': estado,
      'fecha_gestion': now,
    };

    if (nota.isNotEmpty) {
      data['nota_gestor'] = nota;
    }
    if (lat != null && lng != null) {
      data['gps_latitud'] = lat;
      data['gps_longitud'] = lng;
    }
    if (nivel1 != null && nivel1.isNotEmpty) {
      data['nivel_1'] = nivel1;
      data['nivel_2'] = nivel2 ?? '';
      data['nivel_3'] = nivel3 ?? '';
      data['nivel_4'] = nivel4 ?? '';
      data['canal_gestion'] = canalGestion ?? '';
    }
    if (fechaPromesaPago != null && fechaPromesaPago.isNotEmpty) {
      data['fecha_promesa_pago'] = fechaPromesaPago;
    }
    if (montoPromesaPago != null && montoPromesaPago > 0) {
      data['monto_promesa_pago'] = montoPromesaPago;
    }
    if (cartasGestor != null) {
      data['cartas_gestor'] = cartasGestor;
    }

    final clientRef = _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId);

    await clientRef.update(data);

    final histData = <String, dynamic>{
      'estado_gestion': estado,
      'fecha_gestion': now,
      'nota_gestor': nota,
      if (lat != null && lng != null) ...{
        'gps_latitud': lat,
        'gps_longitud': lng,
      },
      if (nivel1 != null && nivel1.isNotEmpty) ...{
        'nivel_1': nivel1,
        'nivel_2': nivel2 ?? '',
        'nivel_3': nivel3 ?? '',
        'nivel_4': nivel4 ?? '',
        'canal_gestion': canalGestion ?? '',
      },
      if (fechaPromesaPago != null && fechaPromesaPago.isNotEmpty)
        'fecha_promesa_pago': fechaPromesaPago,
      if (montoPromesaPago != null && montoPromesaPago > 0)
        'monto_promesa_pago': montoPromesaPago,
      if (gestorUid != null && gestorUid.isNotEmpty) 'gestor_uid': gestorUid,
      if (gestorNombre != null && gestorNombre.isNotEmpty)
        'gestor_nombre': gestorNombre,
      'seccion_key': section,
      'campaign_id': campaignId,
      'client_id': clientId,
    };
    await clientRef.collection('historial_visitas').add(histData);
  }

  /// Update etiquetas assigned to a client.
  Future<void> updateClientTags({
    required String campaignId,
    required String section,
    required String clientId,
    required List<String> etiquetas,
  }) async {
    await _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId)
        .update({'etiquetas': etiquetas});
  }

  /// All active accounts sharing the same DNI (collection group query).
  Future<List<ClientModel>> getAccountsByDocumento(String numeroDocumento) async {
    if (numeroDocumento.trim().isEmpty) return [];
    try {
      final snap = await _db
          .collectionGroup('clientes')
          .where('numero_documento', isEqualTo: numeroDocumento)
          .get();
      return snap.docs
          .map((doc) {
            final data = Map<String, dynamic>.from(doc.data());
            final segments = doc.reference.path.split('/');
            final campIdx = segments.indexOf('campañas');
            final campId = campIdx >= 0 && campIdx + 1 < segments.length
                ? segments[campIdx + 1]
                : 'cartera_activa';
            final gestIdx = segments.indexOf('gestores');
            if (gestIdx >= 0 &&
                gestIdx + 1 < segments.length &&
                (data['seccion_key']?.toString() ?? '').isEmpty) {
              data['seccion_key'] = segments[gestIdx + 1];
            }
            return ClientModel.fromMap(doc.id, data, campaignId: campId);
          })
          .where((c) => c.activoEnCartera)
          .toList();
    } catch (_) {
      return [];
    }
  }

  /// Visit history for a single client account.
  Future<List<VisitaHistorial>> getVisitHistory({
    required String campaignId,
    required String section,
    required String clientId,
    int limit = 50,
  }) async {
    try {
      final snap = await _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(section)
          .collection('clientes')
          .doc(clientId)
          .collection('historial_visitas')
          .limit(limit)
          .get();
      final items = snap.docs
          .map((d) => VisitaHistorial.fromMap(d.id, d.data()))
          .toList();
      items.sort((a, b) {
        final fa = a.fecha ?? DateTime.fromMillisecondsSinceEpoch(0);
        final fb = b.fecha ?? DateTime.fromMillisecondsSinceEpoch(0);
        return fb.compareTo(fa);
      });
      return items;
    } catch (_) {
      return [];
    }
  }

  /// Combined visit history across all accounts with the same DNI.
  Future<List<VisitaHistorial>> getVisitHistoryByDocumento({
    required String numeroDocumento,
    int limit = 80,
  }) async {
    final accounts = await getAccountsByDocumento(numeroDocumento);
    final all = <VisitaHistorial>[];
    for (final acc in accounts) {
      final hist = await getVisitHistory(
        campaignId: acc.campaignId.isNotEmpty ? acc.campaignId : 'cartera_activa',
        section: acc.seccionKey,
        clientId: acc.id,
        limit: limit,
      );
      all.addAll(hist);
    }
    all.sort((a, b) {
      final fa = a.fecha ?? DateTime.fromMillisecondsSinceEpoch(0);
      final fb = b.fecha ?? DateTime.fromMillisecondsSinceEpoch(0);
      return fb.compareTo(fa);
    });
    if (all.length > limit) return all.sublist(0, limit);
    return all;
  }

  /// Request return to central because the gestor cannot access the client's zone.
  Future<void> requestClientReturn({
    required String campaignId,
    required String section,
    required String clientId,
    required String motivo,
    required String nota,
    required double lat,
    required double lng,
    required String gestorUid,
    required String gestorNombre,
    required String gestorEmail,
  }) async {
    final now = DateTime.now().toIso8601String();
    await _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId)
        .update({
      'estado_gestion': 'devolucion_pendiente',
      'fecha_gestion': now,
      'motivo_devolucion': motivo,
      'nota_devolucion': nota,
      'devolucion_solicitada_at': now,
      'devolucion_gestor_uid': gestorUid,
      'devolucion_gestor_nombre': gestorNombre,
      'devolucion_gestor_seccion': section,
      'devolucion_gps_lat': lat,
      'devolucion_gps_lng': lng,
    });
  }

  /// Load a single client document.
  Future<ClientModel?> getClient({
    required String campaignId,
    required String section,
    required String clientId,
  }) async {
    try {
      final snap = await _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(section)
          .collection('clientes')
          .doc(clientId)
          .get();
      if (!snap.exists || snap.data() == null) return null;
      final data = Map<String, dynamic>.from(snap.data()!);
      if ((data['seccion_key']?.toString() ?? '').isEmpty) {
        data['seccion_key'] = section;
      }
      return ClientModel.fromMap(snap.id, data, campaignId: campaignId);
    } catch (e) {
      debugPrint('Error loading client: $e');
      return null;
    }
  }

  /// Contact history events for a client (newest first).
  Future<List<Map<String, dynamic>>> getContactHistory({
    required String campaignId,
    required String section,
    required String clientId,
    int limit = 30,
  }) async {
    try {
      final snap = await _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(section)
          .collection('clientes')
          .doc(clientId)
          .collection('historial_contacto')
          .limit(limit)
          .get();
      final rows = snap.docs.map((d) => {'id': d.id, ...d.data()}).toList();
      rows.sort((a, b) {
        final fa = (a['fecha'] ?? '').toString();
        final fb = (b['fecha'] ?? '').toString();
        return fb.compareTo(fa);
      });
      return rows;
    } catch (e) {
      debugPrint('Error loading contact history: $e');
      return [];
    }
  }

  /// Record field note (observed address/phone) without overwriting bank record.
  Future<String> updateClientContactData({
    required String campaignId,
    required String section,
    required String clientId,
    required String direccionNueva,
    required String telefonoNuevo,
    required String direccionAnterior,
    required String telefonoAnterior,
    required String notaCambio,
    required String editorUid,
    required String editorNombre,
    required String editorEmail,
    required String editorRol,
    double? lat,
    double? lng,
    String nivelConfianza = 'confiable',
    int orden = 0,
  }) async {
    final nowIso = DateTime.now().toIso8601String();
    final clientRef = _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId);

    final phoneTrim = telefonoNuevo.trim();
    final addrTrim = direccionNueva.trim();
    final phoneChanged = phoneTrim.isNotEmpty && phoneTrim != telefonoAnterior.trim();
    final addrChanged = addrTrim.isNotEmpty && addrTrim != direccionAnterior.trim();

    final updateData = <String, dynamic>{
      'ultima_nota_contacto': notaCambio.trim(),
      'fecha_actualizacion_contacto': FieldValue.serverTimestamp(),
      'fecha_actualizacion_contacto_iso': nowIso,
      'actualizado_por_uid': editorUid,
      'actualizado_por_nombre': editorNombre,
      'actualizado_por_email': editorEmail,
      'origen_actualizacion': 'mobile',
    };
    await clientRef.update(updateData);

    final histRef = clientRef.collection('historial_contacto').doc();
    final eventId = histRef.id;
    final tipo = addrChanged && !phoneChanged
        ? 'direccion'
        : phoneChanged && !addrChanged
            ? 'telefono'
            : 'alternativa';

    await histRef.set({
      'fecha': nowIso,
      'fecha_evento': nowIso,
      'campo': 'contacto',
      'tipo': tipo == 'alternativa' ? 'alternativa' : tipo,
      'direccion_anterior': direccionAnterior,
      'direccion_nueva': addrChanged ? addrTrim : '',
      'telefono_anterior': telefonoAnterior,
      'telefono_nuevo': phoneChanged ? phoneTrim : '',
      'nota': notaCambio.trim(),
      'usuario_uid': editorUid,
      'usuario_nombre': editorNombre,
      'usuario_email': editorEmail,
      'rol_editor': editorRol,
      'seccion_key': section,
      'origen_actualizacion': 'mobile',
      'usar_como_principal': false,
      'nivel_confianza': nivelConfianza,
      'orden': orden,
      'oculto': false,
      'es_principal': false,
      'gps': (lat != null && lng != null)
          ? {
              'latitude': lat,
              'longitude': lng,
              'timestamp': nowIso,
            }
          : null,
    });
    return eventId;
  }

  /// Update credibility/order flags on an existing contact history entry.
  Future<void> updateContactEntry({
    required String campaignId,
    required String section,
    required String clientId,
    required String eventId,
    String? nivelConfianza,
    int? orden,
    bool? oculto,
    bool? esPrincipal,
    String? nota,
  }) async {
    final clientRef = _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId);
    final histRef = clientRef.collection('historial_contacto').doc(eventId);
    final data = <String, dynamic>{};
    if (nivelConfianza != null) data['nivel_confianza'] = nivelConfianza;
    if (orden != null) data['orden'] = orden;
    if (oculto != null) data['oculto'] = oculto;
    if (esPrincipal != null) {
      data['es_principal'] = esPrincipal;
      data['usar_como_principal'] = esPrincipal;
    }
    if (nota != null) data['nota'] = nota;
    if (data.isEmpty) return;
    await histRef.update(data);
  }

  /// Load generated letters (JPG) for a client scoped to current gestor.
  Future<List<CartaGenerada>> getClientLetters({
    required String campaignId,
    required String clientId,
    required String section,
  }) async {
    try {
      final uid = _auth.currentUser?.uid ?? '';
      final cartasRef = _db.collection('cartas_generadas');
      final docs = <QueryDocumentSnapshot<Map<String, dynamic>>>[];

      try {
        final qClient = await cartasRef
            .where('campaign_id', isEqualTo: campaignId)
            .where('cliente_id', isEqualTo: clientId)
            .get();
        docs.addAll(qClient.docs);
      } catch (_) {}

      if (uid.isNotEmpty) {
        try {
          final qUid = await cartasRef
              .where('campaign_id', isEqualTo: campaignId)
              .where('cliente_id', isEqualTo: clientId)
              .where('gestor_uid', isEqualTo: uid)
              .get();
          docs.addAll(qUid.docs);
        } catch (_) {}
      }

      try {
        final qSection = await cartasRef
            .where('campaign_id', isEqualTo: campaignId)
            .where('cliente_id', isEqualTo: clientId)
            .where('seccion_key', isEqualTo: section)
            .get();
        docs.addAll(qSection.docs);
      } catch (_) {}

      final map = <String, CartaGenerada>{};
      for (final d in docs) {
        final letter = CartaGenerada.fromMap(d.id, d.data());
        if (letter.mimeType.startsWith('image/')) {
          map[d.id] = letter;
        }
      }
      return map.values.toList();
    } catch (e) {
      debugPrint('Error loading client letters: $e');
      return [];
    }
  }

  // ─────────────────── GPS TRACKING ───────────────────

  /// Save current GPS as the client's verified location (pin for maps/routes).
  /// When [recordHistorial] is true, also appends an audit entry in historial_contacto.
  Future<void> saveVerifiedLocation({
    required String campaignId,
    required String section,
    required String clientId,
    required double lat,
    required double lng,
    double? accuracy,
    required String gestorUid,
    required String gestorNombre,
    String? nota,
    bool recordHistorial = false,
  }) async {
    final nowIso = DateTime.now().toIso8601String();
    final clientRef = _db
        .collection('campañas')
        .doc(campaignId)
        .collection('gestores')
        .doc(section)
        .collection('clientes')
        .doc(clientId);

    await clientRef.update({
      'ubicacion_verificada': {
        'lat': lat,
        'lng': lng,
        'accuracy': accuracy ?? 0,
        'timestamp': nowIso,
        'gestor_uid': gestorUid,
        'gestor_nombre': gestorNombre,
      },
    });

    if (!recordHistorial) return;

    final notaTrim = (nota ?? '').trim();
    final coordLabel =
        '${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}';
    final histRef = clientRef.collection('historial_contacto').doc();
    await histRef.set({
      'fecha': nowIso,
      'fecha_evento': nowIso,
      'campo': 'ubicacion',
      'tipo': 'gps_verificado',
      'direccion_anterior': '',
      'direccion_nueva': 'GPS: $coordLabel',
      'telefono_anterior': '',
      'telefono_nuevo': '',
      'nota': notaTrim.isNotEmpty
          ? notaTrim
          : 'Ubicación GPS verificada en campo ($coordLabel)',
      'usuario_uid': gestorUid,
      'usuario_nombre': gestorNombre,
      'usuario_email': '',
      'rol_editor': 'gestor',
      'seccion_key': section,
      'origen_actualizacion': 'mobile',
      'usar_como_principal': false,
      'nivel_confianza': 'confiable',
      'orden': 0,
      'oculto': false,
      'es_principal': false,
      'gps': {
        'latitude': lat,
        'longitude': lng,
        'accuracy': accuracy ?? 0,
        'timestamp': nowIso,
      },
    });
  }

  // ─────────────────── ZONE EDITING (Admin) ───────────────────

  static const _devolucionFieldKeys = [
    'motivo_devolucion',
    'nota_devolucion',
    'devolucion_solicitada_at',
    'devolucion_gestor_uid',
    'devolucion_gestor_nombre',
    'devolucion_gestor_seccion',
    'devolucion_gps_lat',
    'devolucion_gps_lng',
    'fecha_devolucion_solicitud',
    'gestor_devolucion_uid',
    'gestor_devolucion_nombre',
    'gestor_devolucion_seccion',
  ];

  Map<String, String> _parseSectionComponents(String sectionKey) {
    if (sectionKey.startsWith('_CALL_') ||
        isReservedReassignmentSection(sectionKey)) {
      return {
        'region': '',
        'zona': '',
        'seccion': sectionKey,
      };
    }
    final parts = sectionKey.split('_');
    return {
      'region': parts.isNotEmpty ? parts[0] : '',
      'zona': parts.length > 1 ? parts[1] : '',
      'seccion': parts.length > 2 ? parts[2] : sectionKey,
    };
  }

  Future<void> _updateSectionClientCount(
    DocumentReference campaignRef,
    String seccionKey,
  ) async {
    try {
      final clientsRef = campaignRef
          .collection('gestores')
          .doc(seccionKey)
          .collection('clientes');
      final snap = await clientsRef.get();
      var count = 0;
      var deudaTotal = 0.0;
      var deudaPendiente = 0.0;
      for (final doc in snap.docs) {
        final c = doc.data();
        count++;
        deudaTotal += (c['importe_deuda_asignada'] as num?)?.toDouble() ?? 0;
        deudaPendiente += (c['importe_deuda_pendiente'] as num?)?.toDouble() ?? 0;
      }
      await campaignRef.collection('gestores').doc(seccionKey).update({
        'num_clientes': count,
        'deuda_asignada_total': double.parse(deudaTotal.toStringAsFixed(2)),
        'deuda_pendiente_total': double.parse(deudaPendiente.toStringAsFixed(2)),
      });
    } catch (e) {
      debugPrint('Non-critical: section count update failed: $e');
    }
  }

  /// Move a client from one section to another (admin/supervisor only).
  /// Performs a cross-document move: read → write new → delete old.
  Future<Map<String, dynamic>> updateClientZone({
    required String campaignId,
    required String currentSectionKey,
    required String clientId,
    required String newSectionKey,
    required String adminEmail,
    String adminName = '',
    String motivo = 'edicion_manual',
    bool resetGestion = false,
    Map<String, dynamic>? extraFields,
    List<String>? clearFields,
  }) async {
    if (currentSectionKey == newSectionKey) {
      return {'success': false, 'error': 'La sección origen y destino son iguales.'};
    }

    try {
      final campaignRef = _db.collection('campañas').doc(campaignId);

      final oldRef = campaignRef
          .collection('gestores')
          .doc(currentSectionKey)
          .collection('clientes')
          .doc(clientId);
      final oldDoc = await oldRef.get();
      if (!oldDoc.exists) {
        return {'success': false, 'error': 'Cliente no encontrado en sección actual.'};
      }

      final clientData = Map<String, dynamic>.from(oldDoc.data()!);
      final parsed = _parseSectionComponents(newSectionKey);

      final historial = (clientData['historial_zona'] is List)
          ? List<Map<String, dynamic>>.from(
              (clientData['historial_zona'] as List)
                  .map((e) => Map<String, dynamic>.from(e as Map)))
          : <Map<String, dynamic>>[];
      historial.add({
        'seccion_anterior': currentSectionKey,
        'seccion_nueva': newSectionKey,
        'fecha': DateTime.now().toIso8601String(),
        'admin_email': adminEmail,
        'admin_name': adminName,
        'motivo': motivo,
      });

      clientData['seccion'] = parsed['seccion'];
      clientData['seccion_key'] = newSectionKey;
      clientData['region'] = parsed['region'];
      clientData['zona'] = parsed['zona'];
      clientData['historial_zona'] = historial;

      if (resetGestion) {
        clientData['estado_gestion'] = 'pendiente';
        clientData['nota_gestor'] = '';
        clientData['fecha_gestion'] = '';
        clientData['nivel_1'] = '';
        clientData['nivel_2'] = '';
        clientData['nivel_3'] = '';
        clientData['nivel_4'] = '';
        clientData['canal_gestion'] = '';
        clientData['fecha_promesa_pago'] = '';
        clientData['monto_promesa_pago'] = 0;
        for (final key in _devolucionFieldKeys) {
          clientData.remove(key);
        }
      }

      if (extraFields != null) {
        clientData.addAll(extraFields);
      }
      if (clearFields != null) {
        for (final key in clearFields) {
          clientData.remove(key);
        }
      }

      final newGestorRef = campaignRef.collection('gestores').doc(newSectionKey);
      final newGestorDoc = await newGestorRef.get();
      if (!newGestorDoc.exists) {
        await newGestorRef.set({
          'seccion_key': newSectionKey,
          'seccion': parsed['seccion'],
          'region': parsed['region'],
          'zona': parsed['zona'],
          'num_clientes': 0,
          'deuda_asignada_total': 0,
          'deuda_pendiente_total': 0,
          'fecha_asignacion': FieldValue.serverTimestamp(),
          'estado': 'pendiente',
        });
      }

      final batch = _db.batch();
      final newClientRef = newGestorRef.collection('clientes').doc(clientId);
      batch.set(newClientRef, clientData);
      batch.delete(oldRef);
      await batch.commit();

      await _updateSectionClientCount(campaignRef, currentSectionKey);
      await _updateSectionClientCount(campaignRef, newSectionKey);

      return {
        'success': true,
        'client_id': clientId,
        'client_name': clientData['nombre_completo']?.toString() ?? '',
        'from_section': currentSectionKey,
        'to_section': newSectionKey,
      };
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Clients with estado_gestion=devolucion_pendiente (excluding pool).
  Future<List<Map<String, dynamic>>> listPendingReturns(String campaignId) async {
    final queryResult = await _listPendingReturnsQuery(campaignId);
    if (queryResult != null) return queryResult;
    return _listPendingReturnsScan(campaignId);
  }

  Future<List<Map<String, dynamic>>?> _listPendingReturnsQuery(
    String campaignId,
  ) async {
    final results = <Map<String, dynamic>>[];
    final campaignMarker = '/campañas/$campaignId/gestores/';
    try {
      final snap = await _db
          .collectionGroup('clientes')
          .where('estado_gestion', isEqualTo: 'devolucion_pendiente')
          .get();
      for (final doc in snap.docs) {
        final path = doc.reference.path.replaceAll('\\', '/');
        if (!path.contains(campaignMarker)) continue;
        final parts = path.split('/');
        final gi = parts.indexOf('gestores');
        if (gi < 0 || gi + 1 >= parts.length) continue;
        final secId = parts[gi + 1];
        if (secId == poolReasignacionSectionKey) continue;
        final data = doc.data();
        results.add({
          ...data,
          'codigo_cliente': data['codigo_cliente'] ?? doc.id,
          'client_id': doc.id,
          'seccion_key': secId,
          'campaign_id': campaignId,
        });
      }
      results.sort((a, b) {
        final fa = (a['devolucion_solicitada_at'] ?? a['fecha_gestion'] ?? '')
            .toString();
        final fb = (b['devolucion_solicitada_at'] ?? b['fecha_gestion'] ?? '')
            .toString();
        return fb.compareTo(fa);
      });
      return results;
    } catch (e) {
      final err = e.toString().toLowerCase();
      if (err.contains('index') || err.contains('failed precondition')) {
        debugPrint('Pending returns: collection group index missing, using scan');
        return null;
      }
      debugPrint('Error listing pending returns (query): $e');
      return [];
    }
  }

  Future<List<Map<String, dynamic>>> _listPendingReturnsScan(
    String campaignId,
  ) async {
    final results = <Map<String, dynamic>>[];
    try {
      final campaignRef = _db.collection('campañas').doc(campaignId);
      final gestoresSnap = await campaignRef.collection('gestores').get();
      for (final gestorDoc in gestoresSnap.docs) {
        final secId = gestorDoc.id;
        if (secId == poolReasignacionSectionKey) continue;
        final clientsSnap =
            await gestorDoc.reference.collection('clientes').get();
        for (final cdoc in clientsSnap.docs) {
          final data = cdoc.data();
          if (data['estado_gestion'] != 'devolucion_pendiente') continue;
          results.add({
            ...data,
            'codigo_cliente': data['codigo_cliente'] ?? cdoc.id,
            'client_id': cdoc.id,
            'seccion_key': secId,
            'campaign_id': campaignId,
          });
        }
      }
      results.sort((a, b) {
        final fa = (a['devolucion_solicitada_at'] ?? a['fecha_gestion'] ?? '')
            .toString();
        final fb = (b['devolucion_solicitada_at'] ?? b['fecha_gestion'] ?? '')
            .toString();
        return fb.compareTo(fa);
      });
    } catch (e) {
      debugPrint('Error listing pending returns (scan): $e');
    }
    return results;
  }

  /// Clients in the reassignment pool section.
  Future<List<Map<String, dynamic>>> listPoolClients(String campaignId) async {
    final results = <Map<String, dynamic>>[];
    try {
      final poolRef = _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(poolReasignacionSectionKey)
          .collection('clientes');
      final snap = await poolRef.get();
      for (final doc in snap.docs) {
        final data = doc.data();
        results.add({
          ...data,
          'codigo_cliente': data['codigo_cliente'] ?? doc.id,
          'client_id': doc.id,
          'seccion_key': poolReasignacionSectionKey,
          'campaign_id': campaignId,
        });
      }
    } catch (e) {
      debugPrint('Error listing pool clients: $e');
    }
    return results;
  }

  /// Clients in gestión especial section.
  Future<List<Map<String, dynamic>>> listGestionEspecialClients(
    String campaignId,
  ) async {
    final results = <Map<String, dynamic>>[];
    try {
      final ref = _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(gestionEspecialSectionKey)
          .collection('clientes');
      final snap = await ref.get();
      for (final doc in snap.docs) {
        final data = doc.data();
        results.add({
          ...data,
          'codigo_cliente': data['codigo_cliente'] ?? doc.id,
          'client_id': doc.id,
          'seccion_key': gestionEspecialSectionKey,
          'campaign_id': campaignId,
        });
      }
    } catch (e) {
      debugPrint('Error listing gestión especial clients: $e');
    }
    return results;
  }

  /// Valid destination sections for reassignment (excludes pool/especial).
  Future<List<String>> resolveDestinationSections(String campaignId) async {
    final keys = <String>{};
    final campaignService = CampaignService();
    final campaignSections =
        await campaignService.getAvailableSections(campaignId);
    for (final sid in campaignSections) {
      if (sid.isNotEmpty && !isReservedReassignmentSection(sid)) {
        keys.add(sid);
      }
    }
    final users = await getGestoresActivos();
    for (final user in users) {
      for (final sk in resolveGestorSectionKeys(user)) {
        if (sk.isNotEmpty && !isReservedReassignmentSection(sk)) {
          keys.add(sk);
        }
      }
    }
    final sorted = keys.toList()..sort();
    return sorted;
  }

  /// Move a pending-return client into the reassignment pool.
  Future<Map<String, dynamic>> moveClientToPool({
    required String campaignId,
    required String currentSectionKey,
    required String clientId,
    required String adminEmail,
    String adminName = '',
  }) {
    return updateClientZone(
      campaignId: campaignId,
      currentSectionKey: currentSectionKey,
      clientId: clientId,
      newSectionKey: poolReasignacionSectionKey,
      adminEmail: adminEmail,
      adminName: adminName,
      motivo: 'zona_inaccesible_pool',
      resetGestion: false,
    );
  }

  /// Reassign a returned/pooled client to a gestor section as pendiente.
  Future<Map<String, dynamic>> reassignReturnedClient({
    required String campaignId,
    required String currentSectionKey,
    required String clientId,
    required String newSectionKey,
    required String adminEmail,
    String adminName = '',
    bool notify = true,
    List<UserModel>? gestoresCache,
  }) async {
    if (newSectionKey == poolReasignacionSectionKey) {
      return {
        'success': false,
        'error': 'Seleccione una sección de gestor válida.',
      };
    }
    final result = await updateClientZone(
      campaignId: campaignId,
      currentSectionKey: currentSectionKey,
      clientId: clientId,
      newSectionKey: newSectionKey,
      adminEmail: adminEmail,
      adminName: adminName,
      motivo: 'zona_inaccesible',
      resetGestion: true,
    );
    if (result['success'] == true && notify) {
      final users = gestoresCache ?? await getGestoresActivos();
      final destUid =
          resolveGestorUidForSection(newSectionKey, users) ?? '';
      if (destUid.isNotEmpty) {
        await NotificationService().notifyClientReassigned(
          campaignId: campaignId,
          destinatarioUid: destUid,
          seccionKey: newSectionKey,
          clientId: clientId,
          clientName: result['client_name']?.toString() ?? '',
        );
      }
    }
    return result;
  }

  /// Reject a return request — client stays with original gestor as pendiente.
  Future<Map<String, dynamic>> rejectReturnRequest({
    required String campaignId,
    required String seccionKey,
    required String clientId,
    required String adminEmail,
    String adminName = '',
    String rejectionNote = '',
    List<UserModel>? gestoresCache,
  }) async {
    try {
      final ref = _db
          .collection('campañas')
          .doc(campaignId)
          .collection('gestores')
          .doc(seccionKey)
          .collection('clientes')
          .doc(clientId);
      final doc = await ref.get();
      if (!doc.exists) {
        return {'success': false, 'error': 'Cliente no encontrado.'};
      }
      final data = doc.data() ?? {};
      final gestorUid =
          (data['devolucion_gestor_uid'] ?? data['gestor_devolucion_uid'] ?? '')
              .toString();
      final update = <String, dynamic>{
        'estado_gestion': 'pendiente',
        'nota_gestor': rejectionNote.isNotEmpty
            ? rejectionNote
            : 'Devolución rechazada por central.',
        'devolucion_rechazada_at': DateTime.now().toIso8601String(),
        'devolucion_rechazada_por': adminEmail,
      };
      for (final key in _devolucionFieldKeys) {
        update[key] = FieldValue.delete();
      }
      await ref.update(update);
      if (gestorUid.isNotEmpty) {
        await NotificationService().notifyReturnRejected(
          campaignId: campaignId,
          destinatarioUid: gestorUid,
          seccionKey: seccionKey,
          clientId: clientId,
          rejectionNote: rejectionNote,
        );
      }
      return {'success': true, 'client_id': clientId};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Derive client to gestión especial.
  Future<Map<String, dynamic>> moveClientToGestionEspecial({
    required String campaignId,
    required String currentSectionKey,
    required String clientId,
    required String adminEmail,
    String adminName = '',
    String motivo = 'zona_inaccesible',
  }) {
    return updateClientZone(
      campaignId: campaignId,
      currentSectionKey: currentSectionKey,
      clientId: clientId,
      newSectionKey: gestionEspecialSectionKey,
      adminEmail: adminEmail,
      adminName: adminName,
      motivo: 'gestion_especial',
      resetGestion: true,
      extraFields: {
        'gestion_especial': true,
        'motivo_gestion_especial': motivo,
        'seccion_origen': currentSectionKey,
      },
    );
  }

  /// Restore client from gestión especial to original section.
  Future<Map<String, dynamic>> restoreFromGestionEspecial({
    required String campaignId,
    required String clientId,
    required String seccionOrigen,
    required String adminEmail,
    String adminName = '',
  }) {
    return updateClientZone(
      campaignId: campaignId,
      currentSectionKey: gestionEspecialSectionKey,
      clientId: clientId,
      newSectionKey: seccionOrigen,
      adminEmail: adminEmail,
      adminName: adminName,
      motivo: 'restitucion_gestion_especial',
      resetGestion: true,
      extraFields: {'gestion_especial': false},
      clearFields: ['motivo_gestion_especial', 'seccion_origen'],
    );
  }

  /// Bulk reassignment of multiple clients to the same destination section.
  Future<Map<String, dynamic>> reassignClientsBulk({
    required String campaignId,
    required List<Map<String, String>> clients,
    required String newSectionKey,
    required String adminEmail,
    String adminName = '',
    String motivo = 'reasignacion_manual',
    bool resetGestion = false,
    bool notify = true,
    void Function(int done, int total)? onProgress,
    List<UserModel>? gestoresCache,
  }) async {
    if (newSectionKey == poolReasignacionSectionKey) {
      return {
        'success': false,
        'error': 'Seleccione una sección de gestor válida.',
      };
    }
    var ok = 0;
    var failed = 0;
    final errors = <String>[];
    final total = clients.length;
    for (var i = 0; i < clients.length; i++) {
      final item = clients[i];
      final clientId = item['client_id'] ?? '';
      final fromSection = item['seccion_key'] ?? '';
      if (clientId.isEmpty || fromSection.isEmpty) {
        failed++;
        continue;
      }
      final result = await updateClientZone(
        campaignId: campaignId,
        currentSectionKey: fromSection,
        clientId: clientId,
        newSectionKey: newSectionKey,
        adminEmail: adminEmail,
        adminName: adminName,
        motivo: motivo,
        resetGestion: resetGestion,
      );
      if (result['success'] == true) {
        ok++;
      } else {
        failed++;
        errors.add('$clientId: ${result['error']}');
      }
      onProgress?.call(i + 1, total);
    }
    if (notify && ok > 0) {
      final users = gestoresCache ?? await getGestoresActivos();
      final destUid =
          resolveGestorUidForSection(newSectionKey, users) ?? '';
      if (destUid.isNotEmpty) {
        await NotificationService().notifyClientReassigned(
          campaignId: campaignId,
          destinatarioUid: destUid,
          seccionKey: newSectionKey,
          clientId: 'bulk',
          clientName: '$ok cliente(s)',
          motivo: motivo,
        );
      }
    }
    return {
      'success': failed == 0,
      'ok': ok,
      'failed': failed,
      'errors': errors,
    };
  }

  /// Record a GPS tracking point for the current gestor.
  /// Called automatically when a gestor updates a client's status.
  Future<void> recordTrackingPoint({
    required String gestorUid,
    required double lat,
    required double lng,
    double? accuracy,
    String? clientId,
    String? clientName,
    String? estado,
    String? section,
    String? gestorNombre,
  }) async {
    if (gestorUid.isEmpty) return;
    try {
      final now = DateTime.now();
      await _db
          .collection('ubicaciones_gestores')
          .doc(gestorUid)
          .collection('puntos')
          .add({
        'lat': lat,
        'lng': lng,
        'accuracy': accuracy ?? 0,
        'timestamp': FieldValue.serverTimestamp(),
        'fecha': now.toIso8601String(),
        'fecha_dia': formatFechaDia(now),
        'cliente_id': clientId ?? '',
        'cliente_nombre': clientName ?? '',
        'estado': estado ?? '',
        'seccion': section ?? '',
        'tipo': 'visita',
      });

      await _db.collection('ubicaciones_gestores').doc(gestorUid).set({
        'ultima_lat': lat,
        'ultima_lng': lng,
        'ultima_accuracy': accuracy ?? 0,
        'ultimo_timestamp': FieldValue.serverTimestamp(),
        'ultimo_cliente': clientName ?? '',
        'ultimo_estado': estado ?? '',
        'seccion': section ?? '',
        if (gestorNombre != null && gestorNombre.isNotEmpty)
          'gestor_nombre': gestorNombre,
        'ultimo_tipo': 'visita',
      }, SetOptions(merge: true));
    } catch (e) {
      debugPrint('Error recording tracking point: $e');
    }
  }

  /// Formato YYYY-MM-DD para filtros diarios en tracking.
  static String formatFechaDia(DateTime dt) {
    final y = dt.year;
    final m = dt.month.toString().padLeft(2, '0');
    final d = dt.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  /// Stream de últimas posiciones de todos los gestores (admin/supervisor).
  Stream<List<GestorLocation>> streamGestorLocations() {
    return _db.collection('ubicaciones_gestores').snapshots().map((snap) {
      final list = <GestorLocation>[];
      for (final doc in snap.docs) {
        final loc = GestorLocation.fromFirestore(doc.id, doc.data());
        if (loc != null) list.add(loc);
      }
      return list;
    });
  }

  /// Puntos de recorrido GPS de un gestor (día opcional).
  Future<List<TrailPoint>> getTrackingTrail(
    String gestorUid, {
    DateTime? day,
    int limit = 500,
  }) async {
    if (gestorUid.isEmpty) return [];

    final fechaDia = day != null ? formatFechaDia(day) : null;

    try {
      Query<Map<String, dynamic>> query = _db
          .collection('ubicaciones_gestores')
          .doc(gestorUid)
          .collection('puntos');

      if (fechaDia != null) {
        query = query
            .where('fecha_dia', isEqualTo: fechaDia)
            .orderBy('timestamp')
            .limit(limit);
      } else {
        query = query.orderBy('timestamp', descending: true).limit(limit);
      }

      final snap = await query.get();
      var points = snap.docs
          .map((d) => TrailPoint.fromMap(d.data()))
          .whereType<TrailPoint>()
          .toList();

      if (fechaDia == null) {
        points = points.reversed.toList();
      }
      return points;
    } on FirebaseException catch (e) {
      if (!_isMissingIndexError(e) && fechaDia == null) {
        debugPrint('getTrackingTrail error: $e');
        return [];
      }
      debugPrint('getTrackingTrail fallback: $e');
      return _getTrackingTrailFallback(
        gestorUid: gestorUid,
        fechaDia: fechaDia,
        limit: limit,
      );
    } catch (e) {
      debugPrint('getTrackingTrail error: $e');
      return [];
    }
  }

  Future<List<TrailPoint>> _getTrackingTrailFallback({
    required String gestorUid,
    String? fechaDia,
    int limit = 500,
  }) async {
    final snap = await _db
        .collection('ubicaciones_gestores')
        .doc(gestorUid)
        .collection('puntos')
        .orderBy('timestamp', descending: true)
        .limit(limit)
        .get();

    var points = snap.docs
        .map((d) => TrailPoint.fromMap(d.data()))
        .whereType<TrailPoint>()
        .toList();

    if (fechaDia != null) {
      points = points.where((p) {
        if (p.fechaDia == fechaDia) return true;
        if (p.fechaDia.isNotEmpty) return false;
        return p.fecha.startsWith(fechaDia);
      }).toList();
    }

    points.sort((a, b) {
      final ta = a.timestamp?.millisecondsSinceEpoch ?? 0;
      final tb = b.timestamp?.millisecondsSinceEpoch ?? 0;
      return ta.compareTo(tb);
    });
    return points;
  }

  /// Ruta planificada de un gestor para una fecha (YYYY-MM-DD).
  Future<Map<String, dynamic>?> getGestorRouteByDate(
    String gestorUid,
    String fecha,
  ) async {
    if (gestorUid.isEmpty || fecha.isEmpty) return null;
    try {
      final docId = '${fecha}_$gestorUid';
      final snap = await _db.collection('rutas_diarias').doc(docId).get();
      if (!snap.exists || snap.data() == null) return null;
      return {'id': snap.id, ...snap.data()!};
    } catch (e) {
      debugPrint('getGestorRouteByDate error: $e');
      return null;
    }
  }

  /// Rutas diarias del equipo (admin/supervisor).
  Future<List<Map<String, dynamic>>> getTeamRoutes({
    String? fecha,
    int limit = 50,
  }) async {
    try {
      Query<Map<String, dynamic>> query =
          _db.collection('rutas_diarias').orderBy('fecha', descending: true);

      if (fecha != null && fecha.isNotEmpty) {
        query = query.where('fecha', isEqualTo: fecha);
      }
      if (limit > 0) {
        query = query.limit(limit);
      }

      final snap = await query.get();
      return snap.docs.map((d) => {'id': d.id, ...d.data()}).toList();
    } on FirebaseException catch (e) {
      if (!_isMissingIndexError(e)) {
        debugPrint('getTeamRoutes error: $e');
        return [];
      }
      return _getTeamRoutesFallback(fecha: fecha, limit: limit);
    } catch (e) {
      debugPrint('getTeamRoutes error: $e');
      return [];
    }
  }

  Future<List<Map<String, dynamic>>> _getTeamRoutesFallback({
    String? fecha,
    int limit = 50,
  }) async {
    final snap = await _db.collection('rutas_diarias').limit(limit > 0 ? limit : 100).get();
    var routes = snap.docs.map((d) => {'id': d.id, ...d.data()}).toList();
    if (fecha != null && fecha.isNotEmpty) {
      routes = routes.where((r) => r['fecha']?.toString() == fecha).toList();
    }
    routes.sort((a, b) {
      final fa = a['fecha']?.toString() ?? '';
      final fb = b['fecha']?.toString() ?? '';
      return fb.compareTo(fa);
    });
    if (limit > 0 && routes.length > limit) {
      routes = routes.sublist(0, limit);
    }
    return routes;
  }

  /// Gestores activos para enriquecer nombres en mapa admin.
  Future<List<UserModel>> getGestoresActivos() async {
    final users = await getUsers();
    return users.where((u) => u.isGestor && u.activo).toList();
  }

  // ─────────────────── USERS (Admin) ───────────────────

  /// Deduplicate users by canonical uid (mirrors list_gestor_users in admin-app).
  static List<UserModel> deduplicateUsers(List<UserModel> users) {
    final seen = <String>{};
    final result = <UserModel>[];
    for (final user in users) {
      final canonicalUid =
          user.uid.isNotEmpty ? user.uid : user.email.toLowerCase();
      if (canonicalUid.isEmpty || seen.contains(canonicalUid)) continue;
      seen.add(canonicalUid);
      result.add(user);
    }
    return result;
  }

  /// Get all users.
  Future<List<UserModel>> getUsers() async {
    try {
      final snapshot = await _db.collection('usuarios').get();
      final users = snapshot.docs
          .map((doc) => UserModel.fromMap(doc.id, doc.data()))
          .toList();
      return deduplicateUsers(users);
    } catch (e) {
      debugPrint('Error loading users: $e');
      return [];
    }
  }

  /// Stream real-time user updates.
  Stream<List<UserModel>> streamUsers() {
    return _db.collection('usuarios').snapshots().map((snap) {
      final users = snap.docs
          .map((doc) => UserModel.fromMap(doc.id, doc.data()))
          .toList();
      return deduplicateUsers(users);
    });
  }

  /// Create or update a user.
  Future<void> saveUser(UserModel user) async {
    final data = user.toMap();

    // Write to canonical UID-based doc only
    final docId = user.uid.isNotEmpty ? user.uid : user.email.toLowerCase().replaceAll(RegExp(r'[.@]'), '_');
    await _db.collection('usuarios').doc(docId).set(data, SetOptions(merge: true));
  }

  /// Delete a user document and all duplicate docs for the same email.
  Future<void> deleteUser(String docId) async {
    // Read the doc first to get the email
    final userDoc = await _db.collection('usuarios').doc(docId).get();
    final email = userDoc.data()?['email']?.toString().toLowerCase() ?? '';

    // Delete the main document
    await _db.collection('usuarios').doc(docId).delete();

    // Also delete the email-derived duplicate doc
    if (email.isNotEmpty) {
      final emailId = email.replaceAll(RegExp(r'[.@]'), '_');
      if (emailId != docId) {
        try {
          await _db.collection('usuarios').doc(emailId).delete();
        } catch (_) {} // May not exist
      }

      // Clean up any other docs with the same email
      final query = await _db
          .collection('usuarios')
          .where('email', isEqualTo: email)
          .get();
      for (final doc in query.docs) {
        if (doc.id != docId) {
          await doc.reference.delete();
        }
      }
    }
  }

  /// Sync territorial fields across all docs for a given email.
  Future<void> syncUserSection(
    String email, {
    required String seccion,
    String region = '',
    String zona = '',
    List<String> secciones = const [],
  }) async {
    final emailLower = email.toLowerCase();
    final emailId = emailLower.replaceAll(RegExp(r'[.@]'), '_');
    final updates = <String, dynamic>{
      'seccion': seccion,
      'region': region,
      'zona': zona,
      'secciones': secciones,
    };

    // Update email-derived doc
    try {
      await _db.collection('usuarios').doc(emailId).update(updates);
    } catch (_) {}

    // Update any docs matching this email
    final query = await _db
        .collection('usuarios')
        .where('email', isEqualTo: emailLower)
        .get();
    for (final doc in query.docs) {
      await doc.reference.update(updates);
    }
  }

  // ─────────────────── TERRITORIAL CATALOG ───────────────────

  /// Fetch the territorial catalog (region → zona → secciones hierarchy).
  /// Returns the `regiones` map from `estructura_territorial/catalogo`.
  Future<Map<String, dynamic>> getEstructuraTerritorial() async {
    try {
      final doc = await _db
          .collection('estructura_territorial')
          .doc('catalogo')
          .get();
      if (doc.exists && doc.data() != null) {
        final regiones = doc.data()!['regiones'];
        if (regiones is Map<String, dynamic>) return regiones;
      }
      return {};
    } catch (e) {
      debugPrint('Error loading territorial catalog: $e');
      return {};
    }
  }
}
