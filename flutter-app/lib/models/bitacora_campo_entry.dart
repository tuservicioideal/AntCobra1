import 'package:cloud_firestore/cloud_firestore.dart';

/// Evento del índice denormalizado `bitacora_campo` (consulta admin/supervisor).
class BitacoraCampoEntry {
  static const String tipoUbicacion = 'ubicacion';
  static const String tipoTelegram = 'telegram';
  static const String tipoNotaCampo = 'nota_campo';
  static const String tipoNotaGestion = 'nota_gestion';

  final String id;
  final String tipo;
  final DateTime? creadoAt;
  final String fechaDia;
  final String campaignId;
  final String seccionKey;
  final String clienteId;
  final String clienteNombre;
  final String codigoCliente;
  final String dni;
  final String usuarioUid;
  final String usuarioNombre;
  final String usuarioRol;
  final String resumen;
  final String origenId;
  final String origenColeccion;
  final Map<String, dynamic> payload;

  const BitacoraCampoEntry({
    this.id = '',
    this.tipo = '',
    this.creadoAt,
    this.fechaDia = '',
    this.campaignId = '',
    this.seccionKey = '',
    this.clienteId = '',
    this.clienteNombre = '',
    this.codigoCliente = '',
    this.dni = '',
    this.usuarioUid = '',
    this.usuarioNombre = '',
    this.usuarioRol = '',
    this.resumen = '',
    this.origenId = '',
    this.origenColeccion = '',
    this.payload = const {},
  });

  factory BitacoraCampoEntry.fromMap(String id, Map<String, dynamic> data) {
    DateTime? creado;
    final raw = data['creado_at'];
    if (raw is Timestamp) {
      creado = raw.toDate();
    } else if (raw is DateTime) {
      creado = raw;
    } else if (raw != null) {
      creado = DateTime.tryParse(raw.toString());
    }

    final payloadRaw = data['payload'];
    final payload = payloadRaw is Map
        ? Map<String, dynamic>.from(payloadRaw)
        : <String, dynamic>{};

    return BitacoraCampoEntry(
      id: id,
      tipo: data['tipo']?.toString() ?? '',
      creadoAt: creado,
      fechaDia: data['fecha_dia']?.toString() ?? '',
      campaignId: data['campaign_id']?.toString() ?? '',
      seccionKey: data['seccion_key']?.toString() ?? '',
      clienteId: data['cliente_id']?.toString() ?? '',
      clienteNombre: data['cliente_nombre']?.toString() ?? '',
      codigoCliente: data['codigo_cliente']?.toString() ?? '',
      dni: data['dni']?.toString() ?? '',
      usuarioUid: data['usuario_uid']?.toString() ?? '',
      usuarioNombre: data['usuario_nombre']?.toString() ?? '',
      usuarioRol: data['usuario_rol']?.toString() ?? '',
      resumen: data['resumen']?.toString() ?? '',
      origenId: data['origen_id']?.toString() ?? '',
      origenColeccion: data['origen_coleccion']?.toString() ?? '',
      payload: payload,
    );
  }

  bool get isUbicacion => tipo == tipoUbicacion;
  bool get isTelegram => tipo == tipoTelegram;
  bool get isNotaCampo => tipo == tipoNotaCampo;
  bool get isNotaGestion => tipo == tipoNotaGestion;
  bool get isNota => isNotaCampo || isNotaGestion;

  bool get hasCliente => clienteId.trim().isNotEmpty;

  String get displayType {
    switch (tipo) {
      case tipoUbicacion:
        return 'Ubicación GPS';
      case tipoTelegram:
        return 'Telegram';
      case tipoNotaCampo:
        return 'Nota de campo';
      case tipoNotaGestion:
        return 'Nota de gestión';
      default:
        return tipo.isEmpty ? 'Evento' : tipo;
    }
  }

  String get sortKey => creadoAt?.toIso8601String() ?? '';

  /// IDs deterministas para reintentos / backfill idempotente.
  static String idUbicacion(String histId) => 'ubicacion_$histId';
  static String idTelegram(String jobId) => 'telegram_$jobId';
  static String idNotaCampo(String histId) => 'nota_campo_$histId';
  static String idNotaGestion(String visitaId) => 'nota_gestion_$visitaId';

  static bool matchesLocalQuery(BitacoraCampoEntry e, String q) {
    final needle = q.trim().toLowerCase();
    if (needle.isEmpty) return true;
    return e.clienteNombre.toLowerCase().contains(needle) ||
        e.codigoCliente.toLowerCase().contains(needle) ||
        e.dni.toLowerCase().contains(needle) ||
        e.resumen.toLowerCase().contains(needle) ||
        e.usuarioNombre.toLowerCase().contains(needle);
  }
}
