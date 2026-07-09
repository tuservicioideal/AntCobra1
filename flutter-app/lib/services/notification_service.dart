import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import '../models/notification_model.dart';

/// Service for reading and managing notifications from Firestore.
class NotificationService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  /// Stream of notifications for a specific user (by UID).
  Stream<List<NotificationModel>> streamNotifications(String uid) {
    if (uid.isEmpty) return Stream.value([]);

    return _db
        .collection('notificaciones')
        .where('destinatario_uid', isEqualTo: uid)
        .orderBy('fecha', descending: true)
        .limit(50)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => NotificationModel.fromMap(doc.id, doc.data()))
            .toList())
        .handleError((e) {
      debugPrint('Error streaming notifications: $e');
      return <NotificationModel>[];
    });
  }

  /// Mark a notification as read.
  Future<void> markAsRead(String notifId) async {
    try {
      await _db.collection('notificaciones').doc(notifId).update({
        'leida': true,
      });
    } catch (e) {
      debugPrint('Error marking notification as read: $e');
    }
  }

  /// Notify destination gestor about a reassigned client.
  Future<bool> notifyClientReassigned({
    required String campaignId,
    required String destinatarioUid,
    required String seccionKey,
    required String clientId,
    String clientName = '',
    String motivo = 'zona_inaccesible',
  }) async {
    if (destinatarioUid.isEmpty) return false;
    try {
      await _db.collection('notificaciones').add({
        'tipo': 'cliente_reasignado',
        'destinatario_uid': destinatarioUid,
        'seccion_key': seccionKey,
        'titulo': 'Nuevo cliente reasignado',
        'mensaje':
            'Se le asignó el cliente ${clientName.isNotEmpty ? clientName : clientId} '
            'por reasignación ($motivo).',
        'detalles': {
          'cliente_id': clientId,
          'cliente_nombre': clientName,
        },
        'leida': false,
        'fecha': FieldValue.serverTimestamp(),
        'campaign_id': campaignId,
      });
      return true;
    } catch (e) {
      debugPrint('Error notifying client reassigned: $e');
      return false;
    }
  }

  /// Notify gestor that their return request was rejected.
  Future<bool> notifyReturnRejected({
    required String campaignId,
    required String destinatarioUid,
    required String seccionKey,
    required String clientId,
    String rejectionNote = '',
  }) async {
    if (destinatarioUid.isEmpty) return false;
    try {
      await _db.collection('notificaciones').add({
        'tipo': 'devolucion_rechazada',
        'destinatario_uid': destinatarioUid,
        'seccion_key': seccionKey,
        'titulo': 'Devolución rechazada',
        'mensaje':
            'Su solicitud de devolución para el cliente $clientId fue rechazada. '
            'Debe continuar la gestión.',
        'detalles': {
          'cliente_id': clientId,
          'nota': rejectionNote,
        },
        'leida': false,
        'fecha': FieldValue.serverTimestamp(),
        'campaign_id': campaignId,
      });
      return true;
    } catch (e) {
      debugPrint('Error notifying return rejected: $e');
      return false;
    }
  }

  /// Get unread notification count (one-time).
  Future<int> getUnreadCount(String uid) async {
    if (uid.isEmpty) return 0;
    try {
      final snap = await _db
          .collection('notificaciones')
          .where('destinatario_uid', isEqualTo: uid)
          .where('leida', isEqualTo: false)
          .get();
      return snap.size;
    } catch (e) {
      debugPrint('Error getting unread count: $e');
      return 0;
    }
  }
}
