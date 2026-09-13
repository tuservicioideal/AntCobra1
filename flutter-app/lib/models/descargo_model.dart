import 'package:flutter/material.dart';

/// Tipos de respuesta que el gestor puede registrar como descargo.
/// Cubren los casos de campo: "no soy la persona", "no la conozco", etc.
class DescargoTipos {
  static const noEsTitular = 'no_es_titular';
  static const noConoceTitular = 'no_conoce_titular';
  static const titularFallecido = 'titular_fallecido';
  static const seNegoAPagar = 'se_nego_a_pagar';
  static const pidioNoVolver = 'pidio_no_volver';
  static const otro = 'otro';

  static const List<String> todos = [
    noEsTitular,
    noConoceTitular,
    titularFallecido,
    seNegoAPagar,
    pidioNoVolver,
    otro,
  ];

  static String label(String tipo) {
    switch (tipo) {
      case noEsTitular:
        return 'No es el titular';
      case noConoceTitular:
        return 'No conoce al titular';
      case titularFallecido:
        return 'Titular fallecido (según tercero)';
      case seNegoAPagar:
        return 'Se negó a pagar / atender';
      case pidioNoVolver:
        return 'Pidió no volver / retiro datos';
      case otro:
        return 'Otro descargo';
      default:
        return tipo;
    }
  }

  static IconData icon(String tipo) {
    switch (tipo) {
      case noEsTitular:
        return Icons.person_off_outlined;
      case noConoceTitular:
        return Icons.help_outline;
      case titularFallecido:
        return Icons.sentiment_very_dissatisfied_outlined;
      case seNegoAPagar:
        return Icons.block_outlined;
      case pidioNoVolver:
        return Icons.privacy_tip_outlined;
      default:
        return Icons.record_voice_over_outlined;
    }
  }

  static Color color(String tipo) {
    switch (tipo) {
      case noEsTitular:
        return Colors.orange.shade700;
      case noConoceTitular:
        return Colors.blueGrey.shade700;
      case titularFallecido:
        return Colors.purple.shade700;
      case seNegoAPagar:
        return Colors.red.shade700;
      case pidioNoVolver:
        return Colors.teal.shade700;
      default:
        return Colors.grey.shade700;
    }
  }
}

/// Evidencia adjunta a un descargo (foto o audio subido a Storage).
class DescargoEvidencia {
  final String tipo; // 'foto' | 'audio'
  final String storagePath;
  final String downloadUrl;
  final String mimeType;
  final int sizeBytes;

  const DescargoEvidencia({
    this.tipo = 'foto',
    this.storagePath = '',
    this.downloadUrl = '',
    this.mimeType = '',
    this.sizeBytes = 0,
  });

  bool get isAudio => tipo == 'audio';
  bool get isFoto => tipo != 'audio';

  factory DescargoEvidencia.fromMap(Map<String, dynamic> data) {
    return DescargoEvidencia(
      tipo: data['tipo']?.toString() ?? 'foto',
      storagePath: data['storage_path']?.toString() ?? '',
      downloadUrl: data['download_url']?.toString() ?? '',
      mimeType: data['mime_type']?.toString() ?? '',
      sizeBytes: (data['size_bytes'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toMap() => {
        'tipo': tipo,
        'storage_path': storagePath,
        'download_url': downloadUrl,
        'mime_type': mimeType,
        'size_bytes': sizeBytes,
      };
}

/// Descargo del cliente: lo que respondió la persona contactada.
class DescargoModel {
  final String id;
  final String tipoRespuesta;
  final String texto;
  final String gestorUid;
  final String gestorNombre;
  final DateTime? fecha;
  final double gpsLat;
  final double gpsLng;
  final List<DescargoEvidencia> evidencias;

  const DescargoModel({
    this.id = '',
    this.tipoRespuesta = DescargoTipos.otro,
    this.texto = '',
    this.gestorUid = '',
    this.gestorNombre = '',
    this.fecha,
    this.gpsLat = 0,
    this.gpsLng = 0,
    this.evidencias = const [],
  });

  int get fotoCount => evidencias.where((e) => e.isFoto).length;
  int get audioCount => evidencias.where((e) => e.isAudio).length;
  bool get hasGps => gpsLat != 0 && gpsLng != 0;

  String get fechaFormatted {
    final f = fecha;
    if (f == null) return '—';
    return '${f.day.toString().padLeft(2, '0')}/'
        '${f.month.toString().padLeft(2, '0')}/'
        '${f.year} '
        '${f.hour.toString().padLeft(2, '0')}:'
        '${f.minute.toString().padLeft(2, '0')}';
  }

  factory DescargoModel.fromMap(String id, Map<String, dynamic> data) {
    DateTime? fecha;
    final raw = data['fecha'] ?? data['created_at'] ?? data['fecha_gestion'];
    if (raw != null) {
      if (raw is DateTime) {
        fecha = raw;
      } else if (raw is String) {
        fecha = DateTime.tryParse(raw);
      } else {
        try {
          // ignore: avoid_dynamic_calls
          fecha = (raw as dynamic).toDate() as DateTime?;
        } catch (_) {
          fecha = null;
        }
      }
    }
    final evRaw = data['evidencias'];
    final evidencias = <DescargoEvidencia>[];
    if (evRaw is List) {
      for (final e in evRaw) {
        if (e is Map) {
          evidencias.add(
            DescargoEvidencia.fromMap(Map<String, dynamic>.from(e)),
          );
        }
      }
    }
    return DescargoModel(
      id: id,
      tipoRespuesta: data['tipo_respuesta']?.toString() ?? DescargoTipos.otro,
      texto: data['texto']?.toString() ?? '',
      gestorUid: data['gestor_uid']?.toString() ?? '',
      gestorNombre: data['gestor_nombre']?.toString() ?? '',
      fecha: fecha,
      gpsLat: (data['gps_latitud'] as num?)?.toDouble() ?? 0,
      gpsLng: (data['gps_longitud'] as num?)?.toDouble() ?? 0,
      evidencias: evidencias,
    );
  }
}
