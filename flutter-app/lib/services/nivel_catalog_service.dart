import 'package:cloud_firestore/cloud_firestore.dart';

/// Service to load and cache the nivel management catalog from Firestore.
class NivelCatalogService {
  static NivelCatalogService? _instance;
  factory NivelCatalogService() => _instance ??= NivelCatalogService._();
  NivelCatalogService._();

  Map<String, dynamic>? _cache;

  /// Load catalog from `configuracion/catalogo_niveles`.
  Future<Map<String, dynamic>?> getCatalogo() async {
    if (_cache != null) return _cache;
    try {
      final snap = await FirebaseFirestore.instance
          .collection('configuracion')
          .doc('catalogo_niveles')
          .get();
      if (snap.exists) {
        _cache = snap.data();
        return _cache;
      }
    } catch (e) {
      // ignore — returns null
    }
    return null;
  }

  /// Get the list of nivel entries from the catalog.
  List<Map<String, dynamic>> get niveles {
    if (_cache == null) return [];
    final raw = _cache!['niveles'];
    if (raw is List) return raw.cast<Map<String, dynamic>>();
    return [];
  }

  /// Get available canales.
  List<String> get canales {
    if (_cache == null) return ['CAM', 'TEL'];
    final raw = _cache!['canales'];
    if (raw is List) return raw.cast<String>();
    return ['CAM', 'TEL'];
  }

  /// Build cascading options filtered by current selections.
  CascadingOptions buildOptions({
    required String canal,
    String? n1,
    String? n2,
    String? n3,
  }) {
    var filtered = niveles.toList();
    if (canal.isNotEmpty) {
      filtered = filtered.where((n) => n['canal'] == canal).toList();
    }

    final nivel1Opts = filtered.map((n) => n['nivel1'] as String).toSet().toList()..sort();

    var f2 = filtered;
    if (n1 != null && n1.isNotEmpty) {
      f2 = f2.where((n) => n['nivel1'] == n1).toList();
    }
    final nivel2Opts = f2.map((n) => n['nivel2'] as String).toSet().toList()..sort();

    var f3 = f2;
    if (n2 != null && n2.isNotEmpty) {
      f3 = f3.where((n) => n['nivel2'] == n2).toList();
    }
    final nivel3Opts = f3.map((n) => n['nivel3'] as String).toSet().toList()..sort();

    var f4 = f3;
    if (n3 != null && n3.isNotEmpty) {
      f4 = f4.where((n) => n['nivel3'] == n3).toList();
    }
    final nivel4Opts = f4.map((n) => n['nivel4'] as String).toSet().toList()..sort();

    return CascadingOptions(
      nivel1Opts: nivel1Opts,
      nivel2Opts: nivel2Opts,
      nivel3Opts: nivel3Opts,
      nivel4Opts: nivel4Opts,
    );
  }
}

class CascadingOptions {
  final List<String> nivel1Opts;
  final List<String> nivel2Opts;
  final List<String> nivel3Opts;
  final List<String> nivel4Opts;

  CascadingOptions({
    required this.nivel1Opts,
    required this.nivel2Opts,
    required this.nivel3Opts,
    required this.nivel4Opts,
  });
}
