/// Notification data model matching the Firestore 'notificaciones' collection.
class NotificationModel {
  final String id;
  final String tipo;
  final String seccionKey;
  final String destinatarioUid;
  final String titulo;
  final String mensaje;
  final List<NotificationDetail> detalles;
  final bool leida;
  final DateTime? fecha;
  final String campaignId;

  NotificationModel({
    required this.id,
    this.tipo = 'base_actualizada',
    this.seccionKey = '',
    this.destinatarioUid = '',
    this.titulo = '',
    this.mensaje = '',
    this.detalles = const [],
    this.leida = false,
    this.fecha,
    this.campaignId = '',
  });

  factory NotificationModel.fromMap(String id, Map<String, dynamic> data) {
    final rawDetalles = data['detalles'];
    List<NotificationDetail> detalles = [];
    if (rawDetalles is List) {
      detalles = rawDetalles
          .map((d) => NotificationDetail.fromMap(d is Map<String, dynamic> ? d : {}))
          .toList();
    }

    DateTime? fecha;
    final rawFecha = data['fecha'];
    if (rawFecha != null) {
      try {
        fecha = (rawFecha as dynamic).toDate();
      } catch (_) {}
    }

    return NotificationModel(
      id: id,
      tipo: data['tipo']?.toString() ?? 'base_actualizada',
      seccionKey: data['seccion_key']?.toString() ?? '',
      destinatarioUid: data['destinatario_uid']?.toString() ?? '',
      titulo: data['titulo']?.toString() ?? '',
      mensaje: data['mensaje']?.toString() ?? '',
      detalles: detalles,
      leida: data['leida'] == true,
      fecha: fecha,
      campaignId: data['campaign_id']?.toString() ?? '',
    );
  }

  String get fechaStr {
    if (fecha == null) return '—';
    return '${fecha!.day.toString().padLeft(2, '0')}/'
        '${fecha!.month.toString().padLeft(2, '0')}/'
        '${fecha!.year} '
        '${fecha!.hour.toString().padLeft(2, '0')}:'
        '${fecha!.minute.toString().padLeft(2, '0')}';
  }

  /// Etiqueta legible del tipo de notificación.
  String get tipoLabel {
    switch (tipo) {
      case 'reparto_call':
        return 'Reparto call center';
      case 'base_actualizada':
        return 'Base actualizada';
      case 'cliente_reasignado':
        return 'Cliente reasignado';
      case 'devolucion_rechazada':
        return 'Devolución rechazada';
      default:
        return tipo.replaceAll('_', ' ');
    }
  }

  int get nuevasCuentasCount {
    if (tipo != 'reparto_call') return detalles.length;
    return detalles.where((d) => d.tipo == 'nuevo').length;
  }
}

class NotificationDetail {
  final String tipo;
  final String codigoCliente;
  final String nombre;
  final String mensaje;

  NotificationDetail({
    this.tipo = '',
    this.codigoCliente = '',
    this.nombre = '',
    this.mensaje = '',
  });

  factory NotificationDetail.fromMap(Map<String, dynamic> data) {
    return NotificationDetail(
      tipo: data['tipo']?.toString() ?? '',
      codigoCliente: data['codigo_cliente']?.toString() ?? '',
      nombre: data['nombre']?.toString() ?? '',
      mensaje: data['mensaje']?.toString() ?? '',
    );
  }
}
