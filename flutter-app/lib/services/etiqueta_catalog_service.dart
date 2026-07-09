import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

/// Catálogo global de etiquetas desde `configuracion/etiquetas`.
class EtiquetaCatalogService {
  static EtiquetaCatalogService? _instance;
  factory EtiquetaCatalogService() => _instance ??= EtiquetaCatalogService._();
  EtiquetaCatalogService._();

  List<EtiquetaDef> _cache = [];

  Future<List<EtiquetaDef>> loadCatalogo({bool force = false}) async {
    if (_cache.isNotEmpty && !force) return _cache;
    _cache = await _fetchFromFirestore(soloActivas: true);
    return _cache;
  }

  /// Carga completa para administración (incluye inactivas).
  Future<List<EtiquetaDef>> loadCatalogoAdmin({bool force = false}) async {
    return _fetchFromFirestore(soloActivas: false);
  }

  Future<List<EtiquetaDef>> _fetchFromFirestore({required bool soloActivas}) async {
    try {
      final snap = await FirebaseFirestore.instance
          .collection('configuracion')
          .doc('etiquetas')
          .get();
      if (!snap.exists) return [];
      final data = snap.data() ?? {};
      final raw = data['etiquetas'];
      if (raw is! List) return [];
      final list = raw
          .whereType<Map>()
          .map((m) => EtiquetaDef.fromMap(Map<String, dynamic>.from(m)))
          .where((e) => !soloActivas || e.activa)
          .toList()
        ..sort((a, b) => a.orden.compareTo(b.orden));
      if (soloActivas) _cache = list;
      return list;
    } catch (_) {
      return soloActivas ? _cache : [];
    }
  }

  /// Publica el catálogo completo en Firestore (admin / supervisor).
  Future<void> publishCatalogo(List<EtiquetaDef> etiquetas) async {
    final payload = etiquetas
        .map((e) => {
              'id': e.id,
              'nombre': e.nombre,
              'color': e.colorHex,
              'descripcion': e.descripcion,
              'activa': e.activa,
              'orden': e.orden,
            })
        .toList();
    await FirebaseFirestore.instance.collection('configuracion').doc('etiquetas').set({
      'version': 1,
      'etiquetas': payload,
      'fecha_sync': FieldValue.serverTimestamp(),
    });
    _cache = etiquetas.where((e) => e.activa).toList()
      ..sort((a, b) => a.orden.compareTo(b.orden));
  }

  static String newEtiquetaId() =>
      'etq_${DateTime.now().millisecondsSinceEpoch.toRadixString(16)}';

  List<EtiquetaDef> get etiquetas => List.unmodifiable(_cache);

  EtiquetaDef? findById(String id) {
    for (final e in _cache) {
      if (e.id == id) return e;
    }
    return null;
  }

  void clearCache() => _cache = [];
}

class EtiquetaDef {
  final String id;
  final String nombre;
  final Color color;
  final String descripcion;
  final bool activa;
  final int orden;

  const EtiquetaDef({
    required this.id,
    required this.nombre,
    required this.color,
    this.descripcion = '',
    this.activa = true,
    this.orden = 0,
  });

  factory EtiquetaDef.fromMap(Map<String, dynamic> data) {
    final colorStr = data['color']?.toString() ?? '#3B82F6';
    Color color;
    try {
      final hex = colorStr.replaceFirst('#', '');
      color = Color(int.parse('FF$hex', radix: 16));
    } catch (_) {
      color = const Color(0xFF3B82F6);
    }
    return EtiquetaDef(
      id: data['id']?.toString() ?? '',
      nombre: data['nombre']?.toString() ?? '',
      color: color,
      descripcion: data['descripcion']?.toString() ?? '',
      activa: data['activa'] != false,
      orden: (data['orden'] as num?)?.toInt() ?? 0,
    );
  }

  String get colorHex {
    final v = color.value;
    return '#${(v & 0xFFFFFF).toRadixString(16).padLeft(6, '0').toUpperCase()}';
  }

  EtiquetaDef copyWith({
    String? nombre,
    Color? color,
    String? descripcion,
    bool? activa,
    int? orden,
  }) {
    return EtiquetaDef(
      id: id,
      nombre: nombre ?? this.nombre,
      color: color ?? this.color,
      descripcion: descripcion ?? this.descripcion,
      activa: activa ?? this.activa,
      orden: orden ?? this.orden,
    );
  }
}
