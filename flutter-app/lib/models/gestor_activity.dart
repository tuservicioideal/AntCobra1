class GestorActivityEntry {
  final String id;
  final String source;
  final String type;
  final DateTime? timestamp;
  final String gestorUid;
  final String gestorNombre;
  final String seccionKey;
  final String canalGestor;
  final String campaignId;
  final String clientId;
  final String clientName;
  final String estadoGestion;
  final String nota;
  final String phone;
  final bool launchSuccess;

  const GestorActivityEntry({
    this.id = '',
    this.source = '',
    this.type = '',
    this.timestamp,
    this.gestorUid = '',
    this.gestorNombre = '',
    this.seccionKey = '',
    this.canalGestor = '',
    this.campaignId = '',
    this.clientId = '',
    this.clientName = '',
    this.estadoGestion = '',
    this.nota = '',
    this.phone = '',
    this.launchSuccess = true,
  });

  factory GestorActivityEntry.fromMap(String id, Map<String, dynamic> data) {
    DateTime? parsedTimestamp;
    final rawTimestamp = data['timestamp'] ?? data['fecha_gestion'] ?? data['fecha'];
    if (rawTimestamp is DateTime) {
      parsedTimestamp = rawTimestamp;
    } else if (rawTimestamp != null) {
      parsedTimestamp = DateTime.tryParse(rawTimestamp.toString());
    }

    return GestorActivityEntry(
      id: id,
      source: data['source']?.toString() ?? '',
      type: data['type']?.toString() ?? '',
      timestamp: parsedTimestamp,
      gestorUid: data['gestor_uid']?.toString() ?? '',
      gestorNombre: data['gestor_nombre']?.toString() ?? '',
      seccionKey: data['seccion_key']?.toString() ?? '',
      canalGestor: data['canal_gestor']?.toString() ?? '',
      campaignId: data['campaign_id']?.toString() ?? '',
      clientId: data['client_id']?.toString() ?? '',
      clientName: data['client_name']?.toString() ?? '',
      estadoGestion: data['estado_gestion']?.toString() ?? '',
      nota: data['nota']?.toString() ?? data['nota_gestor']?.toString() ?? '',
      phone: data['phone']?.toString() ?? '',
      launchSuccess: data['launch_success'] != false,
    );
  }

  bool get isGestion => source == 'historial_visitas';
  bool get isContactAction => source == 'activity_event';
  bool get isCallAttempt => type == 'llamada_iniciada';
  bool get isWhatsAppAttempt => type == 'whatsapp_abierto';

  String get sortKey => timestamp?.toIso8601String() ?? '';

  String get displayType {
    switch (type) {
      case 'gestion_registrada':
        return 'Gestión registrada';
      case 'llamada_iniciada':
        return 'Llamada iniciada';
      case 'whatsapp_abierto':
        return 'WhatsApp abierto';
      default:
        return type.isEmpty ? 'Actividad' : type;
    }
  }
}
