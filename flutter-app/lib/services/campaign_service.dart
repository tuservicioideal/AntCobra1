import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';

import '../utils/section_load_utils.dart';

/// Discovers the active campaign from Firestore.
/// Mirrors campaignUtils.js: checks 'cartera_activa' first, then
/// falls back to latest CAM_* document by ID.
class CampaignService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  String? _activeCampaignId;
  String? _cachedSectionsCampaignId;
  List<String>? _cachedSections;

  String? get activeCampaignId => _activeCampaignId;

  /// Returns the active campaign ID.
  Future<String?> getActiveCampaignId() async {
    if (_activeCampaignId != null) return _activeCampaignId;

    try {
      // 1. Check if 'cartera_activa' document exists (matches web logic)
      final activeDoc = await _db
          .collection('campañas')
          .doc('cartera_activa')
          .get()
          .timeout(const Duration(seconds: 15));
      if (activeDoc.exists) {
        _activeCampaignId = 'cartera_activa';
        return _activeCampaignId;
      }

      // 2. Fallback: find latest CAM_* by ID
      final snapshot = await _db
          .collection('campañas')
          .get()
          .timeout(const Duration(seconds: 15));
      final camDocs = snapshot.docs
          .where((doc) => doc.id.startsWith('CAM_'))
          .toList();

      if (camDocs.isNotEmpty) {
        camDocs.sort((a, b) => b.id.compareTo(a.id));
        _activeCampaignId = camDocs.first.id;
        return _activeCampaignId;
      }
    } catch (e) {
      debugPrint('Error getting active campaign: $e');
    }

    return null;
  }

  /// Get campaign metadata (tramo_actual, dias, etc.)
  /// Con timeout: sin esto un WebChannel colgado deja el panel en spinner eterno.
  Future<Map<String, dynamic>?> getCampaignData(String campaignId) async {
    try {
      final doc = await _db
          .collection('campañas')
          .doc(campaignId)
          .get()
          .timeout(const Duration(seconds: 15));
      return doc.data();
    } catch (e) {
      debugPrint('Error getting campaign data: $e');
      return null;
    }
  }

  /// Discover section keys under `campañas/{id}/gestores`.
  ///
  /// [onlyWithClients] skips empty leftover folders (there can be hundreds)
  /// so web admin stats do not open 500+ Firestore streams at once.
  Future<List<String>> getAvailableSections(
    String campaignId, {
    bool onlyWithClients = false,
  }) async {
    if (!onlyWithClients &&
        _cachedSectionsCampaignId == campaignId &&
        _cachedSections != null) {
      return List<String>.from(_cachedSections!);
    }

    try {
      final campaignRef = _db.collection('campañas').doc(campaignId);
      final gestoresSnap = await campaignRef
          .collection('gestores')
          .get()
          .timeout(const Duration(seconds: 20));
      final hints = gestoresSnap.docs.map((d) {
        final raw = d.data()['num_clientes'];
        int? n;
        if (raw is num) n = raw.toInt();
        return GestorSectionHint(id: d.id, numClientes: n);
      }).toList();

      List<dynamic>? metaSecciones;
      if (onlyWithClients) {
        final campaignSnap =
            await campaignRef.get().timeout(const Duration(seconds: 15));
        metaSecciones = campaignSnap.data()?['secciones'] as List<dynamic>?;
      }

      final ids = onlyWithClients
          ? resolveLoadableSectionIds(
              campaignSecciones: metaSecciones,
              hints: hints,
            )
          : (hints.map((h) => h.id).toList()..sort());

      if (!onlyWithClients) {
        _cachedSectionsCampaignId = campaignId;
        _cachedSections = ids;
      }
      return ids;
    } catch (e) {
      debugPrint('Error getting sections: $e');
      return [];
    }
  }

  /// Clear cached campaign ID.
  void clearCache() {
    _activeCampaignId = null;
    _cachedSectionsCampaignId = null;
    _cachedSections = null;
  }
}
