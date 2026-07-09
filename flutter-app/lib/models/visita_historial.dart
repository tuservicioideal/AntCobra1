/// Historial append-only de visitas/gestiones de un cliente.
class VisitaHistorial {
  final String id;
  final String clientId;
  final String seccionKey;
  final String campaignId;
  final String estadoGestion;
  final String notaGestor;
  final String nivel1;
  final String nivel2;
  final String nivel3;
  final String nivel4;
  final String canalGestion;
  final String fechaPromesaPago;
  final double montoPromesaPago;
  final double gpsLatitud;
  final double gpsLongitud;
  final String gestorUid;
  final String gestorNombre;
  final DateTime? fecha;

  const VisitaHistorial({
    this.id = '',
    this.clientId = '',
    this.seccionKey = '',
    this.campaignId = '',
    this.estadoGestion = '',
    this.notaGestor = '',
    this.nivel1 = '',
    this.nivel2 = '',
    this.nivel3 = '',
    this.nivel4 = '',
    this.canalGestion = '',
    this.fechaPromesaPago = '',
    this.montoPromesaPago = 0,
    this.gpsLatitud = 0,
    this.gpsLongitud = 0,
    this.gestorUid = '',
    this.gestorNombre = '',
    this.fecha,
  });

  factory VisitaHistorial.fromMap(String id, Map<String, dynamic> data) {
    DateTime? fecha;
    final rawFecha = data['fecha_gestion'] ?? data['fecha'] ?? data['fecha_evento'];
    if (rawFecha != null) {
      fecha = DateTime.tryParse(rawFecha.toString());
    }

    return VisitaHistorial(
      id: id,
      clientId: data['client_id']?.toString() ?? '',
      seccionKey: data['seccion_key']?.toString() ?? '',
      campaignId: data['campaign_id']?.toString() ?? '',
      estadoGestion: data['estado_gestion']?.toString() ?? '',
      notaGestor: data['nota_gestor']?.toString() ?? '',
      nivel1: data['nivel_1']?.toString() ?? '',
      nivel2: data['nivel_2']?.toString() ?? '',
      nivel3: data['nivel_3']?.toString() ?? '',
      nivel4: data['nivel_4']?.toString() ?? '',
      canalGestion: data['canal_gestion']?.toString() ?? '',
      fechaPromesaPago: data['fecha_promesa_pago']?.toString() ?? '',
      montoPromesaPago: (data['monto_promesa_pago'] as num?)?.toDouble() ?? 0,
      gpsLatitud: (data['gps_latitud'] as num?)?.toDouble() ?? 0,
      gpsLongitud: (data['gps_longitud'] as num?)?.toDouble() ?? 0,
      gestorUid: data['gestor_uid']?.toString() ?? '',
      gestorNombre: data['gestor_nombre']?.toString() ?? '',
      fecha: fecha,
    );
  }

  String get fechaFormatted {
    if (fecha == null) return '—';
    final d = fecha!;
    return '${d.day.toString().padLeft(2, '0')}/'
        '${d.month.toString().padLeft(2, '0')}/'
        '${d.year} '
        '${d.hour.toString().padLeft(2, '0')}:'
        '${d.minute.toString().padLeft(2, '0')}';
  }
}
