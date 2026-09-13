import 'package:cloud_firestore/cloud_firestore.dart';

import '../utils/caso_problema.dart';

/// Caso de problema en el embudo del resolutor.
class CasoModel {
  final String id;
  final String tipo;
  final String etapa;
  final bool abierto;
  final String campaniaId;
  final String seccion;
  final String seccionKey;
  final String clienteId;
  final String clienteCodigo;
  final String clienteNombre;
  final String clienteDni;
  final String telefono;
  final String direccion;
  final String distrito;
  final double deudaAsignada;
  final double deudaPendiente;
  final String campanaBanco;
  final String notaOrigen;
  final double? gpsLatitud;
  final double? gpsLongitud;
  final String gestorUid;
  final String gestorNombre;
  final String gestorEmail;
  final DateTime? fechaApertura;
  final DateTime? fechaEtapa;
  final String actualizadoPorUid;
  final String actualizadoPorNombre;

  const CasoModel({
    required this.id,
    this.tipo = '',
    this.etapa = 'nuevo',
    this.abierto = true,
    this.campaniaId = '',
    this.seccion = '',
    this.seccionKey = '',
    this.clienteId = '',
    this.clienteCodigo = '',
    this.clienteNombre = '',
    this.clienteDni = '',
    this.telefono = '',
    this.direccion = '',
    this.distrito = '',
    this.deudaAsignada = 0,
    this.deudaPendiente = 0,
    this.campanaBanco = '',
    this.notaOrigen = '',
    this.gpsLatitud,
    this.gpsLongitud,
    this.gestorUid = '',
    this.gestorNombre = '',
    this.gestorEmail = '',
    this.fechaApertura,
    this.fechaEtapa,
    this.actualizadoPorUid = '',
    this.actualizadoPorNombre = '',
  });

  factory CasoModel.fromMap(String id, Map<String, dynamic> data) {
    return CasoModel(
      id: id,
      tipo: data['tipo']?.toString() ?? '',
      etapa: data['etapa']?.toString() ?? 'nuevo',
      abierto: data['abierto'] == true ||
          (data['abierto'] == null &&
              isEtapaAbierta(data['etapa']?.toString() ?? 'nuevo')),
      campaniaId: data['campaña_id']?.toString() ??
          data['campaign_id']?.toString() ??
          '',
      seccion: data['seccion']?.toString() ?? '',
      seccionKey: data['seccion_key']?.toString() ??
          data['seccion']?.toString() ??
          '',
      clienteId: data['cliente_id']?.toString() ?? '',
      clienteCodigo: data['cliente_codigo']?.toString() ?? '',
      clienteNombre: data['cliente_nombre']?.toString() ?? '',
      clienteDni: data['cliente_dni']?.toString() ?? '',
      telefono: data['telefono']?.toString() ?? '',
      direccion: data['direccion']?.toString() ?? '',
      distrito: data['distrito']?.toString() ?? '',
      deudaAsignada: _toDouble(data['deuda_asignada']),
      deudaPendiente: _toDouble(data['deuda_pendiente']),
      campanaBanco: data['campana_banco']?.toString() ?? '',
      notaOrigen: data['nota_origen']?.toString() ?? '',
      gpsLatitud: _toDoubleOrNull(data['gps_latitud']),
      gpsLongitud: _toDoubleOrNull(data['gps_longitud']),
      gestorUid: data['gestor_uid']?.toString() ?? '',
      gestorNombre: data['gestor_nombre']?.toString() ?? '',
      gestorEmail: data['gestor_email']?.toString() ?? '',
      fechaApertura: _toDate(data['fecha_apertura']),
      fechaEtapa: _toDate(data['fecha_etapa']),
      actualizadoPorUid: data['actualizado_por_uid']?.toString() ?? '',
      actualizadoPorNombre: data['actualizado_por_nombre']?.toString() ?? '',
    );
  }

  String get tipoLabel => casoTipoLabel(tipo);
  String get etapaLabel => casoEtapaLabel(etapa);
  bool get isCerrado => isEtapaCerrada(etapa);

  static double _toDouble(dynamic v) {
    if (v is num) return v.toDouble();
    return double.tryParse(v?.toString() ?? '') ?? 0;
  }

  static double? _toDoubleOrNull(dynamic v) {
    if (v == null) return null;
    if (v is num) return v.toDouble();
    return double.tryParse(v.toString());
  }

  static DateTime? _toDate(dynamic v) {
    if (v == null) return null;
    if (v is Timestamp) return v.toDate();
    if (v is DateTime) return v;
    return DateTime.tryParse(v.toString());
  }
}

class CasoComentario {
  final String id;
  final String texto;
  final String uid;
  final String nombre;
  final DateTime? fecha;

  const CasoComentario({
    required this.id,
    this.texto = '',
    this.uid = '',
    this.nombre = '',
    this.fecha,
  });

  factory CasoComentario.fromMap(String id, Map<String, dynamic> data) {
    return CasoComentario(
      id: id,
      texto: data['texto']?.toString() ?? '',
      uid: data['uid']?.toString() ?? '',
      nombre: data['nombre']?.toString() ?? '',
      fecha: CasoModel._toDate(data['fecha']),
    );
  }
}

class CasoMovimiento {
  final String id;
  final String de;
  final String a;
  final String uid;
  final String nombre;
  final String motivo;
  final DateTime? fecha;

  const CasoMovimiento({
    required this.id,
    this.de = '',
    this.a = '',
    this.uid = '',
    this.nombre = '',
    this.motivo = '',
    this.fecha,
  });

  factory CasoMovimiento.fromMap(String id, Map<String, dynamic> data) {
    return CasoMovimiento(
      id: id,
      de: data['de']?.toString() ?? '',
      a: data['a']?.toString() ?? '',
      uid: data['uid']?.toString() ?? '',
      nombre: data['nombre']?.toString() ?? '',
      motivo: data['motivo']?.toString() ?? '',
      fecha: CasoModel._toDate(data['fecha']),
    );
  }
}
