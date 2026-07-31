import 'dart:math';

import 'package:cloud_firestore/cloud_firestore.dart';

/// Última posición conocida de un gestor (doc `ubicaciones_gestores/{uid}`).
class GestorLocation {
  final String uid;
  final String nombre;
  final String seccion;
  final double lat;
  final double lng;
  final double accuracy;
  final Timestamp? timestamp;
  final String ultimoCliente;
  final String ultimoEstado;
  final String tipo;

  const GestorLocation({
    required this.uid,
    required this.nombre,
    required this.seccion,
    required this.lat,
    required this.lng,
    required this.accuracy,
    this.timestamp,
    this.ultimoCliente = '',
    this.ultimoEstado = '',
    this.tipo = '',
  });

  static GestorLocation? fromFirestore(String uid, Map<String, dynamic> data) {
    final lat = _toDouble(data['ultima_lat']);
    final lng = _toDouble(data['ultima_lng']);
    if (lat == null || lng == null || (lat == 0 && lng == 0)) return null;

    final rawName = data['gestor_nombre']?.toString() ?? '';
    return GestorLocation(
      uid: uid,
      nombre: rawName.isNotEmpty ? rawName : uid.substring(0, 8),
      seccion: data['seccion']?.toString() ?? '?',
      lat: lat,
      lng: lng,
      accuracy: _toDouble(data['ultima_accuracy']) ?? 0,
      timestamp: data['ultimo_timestamp'] as Timestamp?,
      ultimoCliente: data['ultimo_cliente']?.toString() ?? '',
      ultimoEstado: data['ultimo_estado']?.toString() ?? '',
      tipo: data['ultimo_tipo']?.toString() ?? '',
    );
  }

  GestorLocation copyWith({String? nombre}) => GestorLocation(
        uid: uid,
        nombre: nombre ?? this.nombre,
        seccion: seccion,
        lat: lat,
        lng: lng,
        accuracy: accuracy,
        timestamp: timestamp,
        ultimoCliente: ultimoCliente,
        ultimoEstado: ultimoEstado,
        tipo: tipo,
      );

  bool get isOnline {
    if (timestamp == null) return false;
    return DateTime.now().difference(timestamp!.toDate()).inMinutes < 5;
  }
}

/// Punto de la subcolección `puntos`.
class TrailPoint {
  final double lat;
  final double lng;
  final String fecha;
  final String fechaDia;
  final String tipo;
  final String cliente;
  final String clienteId;
  final String estado;
  final double accuracy;
  final Timestamp? timestamp;

  const TrailPoint({
    required this.lat,
    required this.lng,
    required this.fecha,
    this.fechaDia = '',
    this.tipo = 'auto',
    this.cliente = '',
    this.clienteId = '',
    this.estado = '',
    this.accuracy = 0,
    this.timestamp,
  });

  static TrailPoint? fromMap(Map<String, dynamic> d) {
    final lat = _toDouble(d['lat']);
    final lng = _toDouble(d['lng']);
    if (lat == null || lng == null) return null;
    return TrailPoint(
      lat: lat,
      lng: lng,
      fecha: d['fecha']?.toString() ?? '',
      fechaDia: d['fecha_dia']?.toString() ?? '',
      tipo: d['tipo']?.toString() ?? 'visita',
      cliente: d['cliente_nombre']?.toString() ?? '',
      clienteId: d['cliente_id']?.toString() ?? '',
      estado: d['estado']?.toString() ?? '',
      accuracy: _toDouble(d['accuracy']) ?? 0,
      timestamp: d['timestamp'] as Timestamp?,
    );
  }

  bool get isVisit => tipo != 'auto';
}

/// Utilidades geográficas para recorridos.
class TrackingGeo {
  TrackingGeo._();

  static double haversineKm(double lat1, double lng1, double lat2, double lng2) {
    const r = 6371.0;
    final dLat = _toRad(lat2 - lat1);
    final dLng = _toRad(lng2 - lng1);
    final a = sin(dLat / 2) * sin(dLat / 2) +
        cos(_toRad(lat1)) *
            cos(_toRad(lat2)) *
            sin(dLng / 2) *
            sin(dLng / 2);
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));
    return r * c;
  }

  static double trailKm(List<TrailPoint> points) {
    if (points.length < 2) return 0;
    var km = 0.0;
    for (var i = 1; i < points.length; i++) {
      km += haversineKm(
        points[i - 1].lat,
        points[i - 1].lng,
        points[i].lat,
        points[i].lng,
      );
    }
    return km;
  }

  /// Ordena clientes de ruta planificada por vecino más cercano.
  static List<Map<String, dynamic>> orderRouteClients(
    List<Map<String, dynamic>> clients, {
    double? originLat,
    double? originLng,
  }) {
    final pending = clients
        .where((c) => c['lat'] != null && c['lng'] != null)
        .map((c) => Map<String, dynamic>.from(c))
        .toList();
    if (pending.isEmpty) return [];

    final ordered = <Map<String, dynamic>>[];
    var currentLat = originLat ?? (pending.first['lat'] as num).toDouble();
    var currentLng = originLng ?? (pending.first['lng'] as num).toDouble();

    while (pending.isNotEmpty) {
      var bestIndex = 0;
      var bestKm = double.infinity;
      for (var i = 0; i < pending.length; i++) {
        final lat = (pending[i]['lat'] as num).toDouble();
        final lng = (pending[i]['lng'] as num).toDouble();
        final d = haversineKm(currentLat, currentLng, lat, lng);
        if (d < bestKm) {
          bestKm = d;
          bestIndex = i;
        }
      }
      final next = pending.removeAt(bestIndex);
      ordered.add(next);
      currentLat = (next['lat'] as num).toDouble();
      currentLng = (next['lng'] as num).toDouble();
    }
    return ordered;
  }
}

double? _toDouble(dynamic val) {
  if (val == null) return null;
  if (val is double) return val;
  if (val is int) return val.toDouble();
  if (val is String) return double.tryParse(val);
  return null;
}

double _toRad(double deg) => deg * pi / 180;
