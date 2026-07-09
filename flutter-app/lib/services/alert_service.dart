import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';

/// Creates alerts in the Firestore 'alertas' collection.
/// Mirrors alertService.js.
class AlertService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  /// Create an alert for suplantacion, pago_no_registrado, or zona_inaccesible_devolucion.
  Future<void> createAlert({
    required String tipo,
    required String campaignId,
    required String section,
    required String clientId,
    required String clientName,
    required String clientDni,
    String nota = '',
    double? lat,
    double? lng,
    String gestorEmail = '',
    String gestorName = '',
  }) async {
    try {
      await _db.collection('alertas').add({
        'tipo': tipo,
        'campaña_id': campaignId,
        'seccion': section,
        'cliente_id': clientId,
        'cliente_nombre': clientName,
        'cliente_dni': clientDni,
        'nota': nota,
        'gps_latitud': lat,
        'gps_longitud': lng,
        'gestor_email': gestorEmail,
        'gestor_nombre': gestorName,
        'estado_alerta': 'pendiente',
        'fecha': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      debugPrint('Error creating alert: $e');
      rethrow;
    }
  }
}
