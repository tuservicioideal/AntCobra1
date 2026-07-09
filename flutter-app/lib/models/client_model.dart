/// Client data model matching the Firestore document structure.
class CartaGenerada {
  final String id;
  final String nombreArchivo;
  final String mimeType;
  final String storagePath;
  final int numeroCarta;

  const CartaGenerada({
    this.id = '',
    this.nombreArchivo = '',
    this.mimeType = '',
    this.storagePath = '',
    this.numeroCarta = 0,
  });

  factory CartaGenerada.fromMap(String id, Map<String, dynamic> data) {
    return CartaGenerada(
      id: id,
      nombreArchivo: data['nombre_archivo']?.toString() ?? '',
      mimeType: data['mime_type']?.toString() ?? '',
      storagePath: data['storage_path']?.toString() ?? '',
      numeroCarta: (data['numero_carta'] as num?)?.toInt() ?? 0,
    );
  }
}

class ClientModel {
  final String id;
  final String campaignId;
  final String codigoCliente;
  final String nombreCompleto;
  final String nombres;
  final String apellidoPaterno;
  final String apellidoMaterno;
  final String numeroDocumento;
  final String telefonoMovil;
  final String correo;
  final String direccion;
  final String distrito;
  final String provincia;
  final String departamento;
  final String referencia;
  final String seccion;
  final String seccionKey;
  /// Número de campaña del banco (columna Excel E), ej. "202516".
  final String campanaBanco;
  final int diasAtraso;
  final double importeDeudaAsignada;
  final double importeDeudaPendiente;
  final String estadoGestion;
  final String notaGestor;
  final int tramoActual;
  final String fechaGestion;
  final double coordenadaX;
  final double coordenadaY;
  final double ubicacionVerificadaLat;
  final double ubicacionVerificadaLng;
  final String ubicacionVerificadaGestor;
  final String ubicacionVerificadaFecha;
  final List<CartaGenerada> cartasGestor;
  final String fechaPromesaPago;
  final double montoPromesaPago;
  final String nivel1;
  final String nivel2;
  final String nivel3;
  final String nivel4;
  final String canalGestion;
  final String actualizadoPorUid;
  final String actualizadoPorNombre;
  /// False when client was removed from bank Excel (soft archive).
  final bool activoEnCartera;
  final String fechaAsignacion;
  final int diaCiclo;
  final String estadoCiclo;
  final bool gestionEspecial;
  final String motivoGestionEspecial;
  final List<String> etiquetas;
  final int cuentasMismoDni;

  ClientModel({
    required this.id,
    this.campaignId = '',
    this.codigoCliente = '',
    this.nombreCompleto = '',
    this.nombres = '',
    this.apellidoPaterno = '',
    this.apellidoMaterno = '',
    this.numeroDocumento = '',
    this.telefonoMovil = '',
    this.correo = '',
    this.direccion = '',
    this.distrito = '',
    this.provincia = '',
    this.departamento = '',
    this.referencia = '',
    this.seccion = '',
    this.seccionKey = '',
    this.campanaBanco = '',
    this.diasAtraso = 0,
    this.importeDeudaAsignada = 0.0,
    this.importeDeudaPendiente = 0.0,
    this.estadoGestion = 'pendiente',
    this.notaGestor = '',
    this.tramoActual = 1,
    this.fechaGestion = '',
    this.coordenadaX = 0.0,
    this.coordenadaY = 0.0,
    this.ubicacionVerificadaLat = 0.0,
    this.ubicacionVerificadaLng = 0.0,
    this.ubicacionVerificadaGestor = '',
    this.ubicacionVerificadaFecha = '',
    this.cartasGestor = const [],
    this.fechaPromesaPago = '',
    this.montoPromesaPago = 0.0,
    this.nivel1 = '',
    this.nivel2 = '',
    this.nivel3 = '',
    this.nivel4 = '',
    this.canalGestion = '',
    this.actualizadoPorUid = '',
    this.actualizadoPorNombre = '',
    this.activoEnCartera = true,
    this.fechaAsignacion = '',
    this.diaCiclo = 1,
    this.estadoCiclo = 'activa',
    this.gestionEspecial = false,
    this.motivoGestionEspecial = '',
    this.etiquetas = const [],
    this.cuentasMismoDni = 1,
  });

  static List<String> _parseEtiquetas(dynamic raw) {
    if (raw is List) {
      return raw.map((e) => e.toString()).where((e) => e.isNotEmpty).toList();
    }
    return const [];
  }

  static bool _parseActivoEnCartera(Map<String, dynamic> data) {
    final v = data['activo_en_cartera'];
    if (v is bool) return v;
    if (v == null) return true;
    return v.toString().toLowerCase() != 'false';
  }

  static double _toDouble(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0.0;
  }

  /// Resuelve coordenadas desde registro banco, visita verificada o GPS de gestión.
  static ({double x, double y}) resolveCoordinates(Map<String, dynamic> data) {
    var x = _toDouble(data['coordenada_x']);
    var y = _toDouble(data['coordenada_y']);

    if (x != 0 && y != 0) return (x: x, y: y);

    final verified = data['ubicacion_verificada'];
    if (verified is Map) {
      final lat = _toDouble(verified['lat']);
      final lng = _toDouble(verified['lng']);
      if (lat != 0 && lng != 0) return (x: lng, y: lat);
    }

    final gpsLat = _toDouble(data['gps_latitud']);
    final gpsLng = _toDouble(data['gps_longitud']);
    if (gpsLat != 0 && gpsLng != 0) return (x: gpsLng, y: gpsLat);

    return (x: x, y: y);
  }

  static ({double lat, double lng, String gestor, String fecha}) _parseUbicacionVerificada(
    Map<String, dynamic> data,
  ) {
    final verified = data['ubicacion_verificada'];
    if (verified is! Map) {
      return (lat: 0.0, lng: 0.0, gestor: '', fecha: '');
    }
    final lat = _toDouble(verified['lat']);
    final lng = _toDouble(verified['lng']);
    return (
      lat: lat,
      lng: lng,
      gestor: verified['gestor_nombre']?.toString() ?? '',
      fecha: verified['timestamp']?.toString() ?? '',
    );
  }

  factory ClientModel.fromMap(String id, Map<String, dynamic> data, {String campaignId = ''}) {
    final coords = resolveCoordinates(data);
    final uv = _parseUbicacionVerificada(data);
    return ClientModel(
      id: id,
      campaignId: campaignId,
      codigoCliente: data['codigo_cliente']?.toString() ?? '',
      nombreCompleto: data['nombre_completo']?.toString() ?? '',
      nombres: data['nombres']?.toString() ?? '',
      apellidoPaterno: data['apellido_paterno']?.toString() ?? '',
      apellidoMaterno: data['apellido_materno']?.toString() ?? '',
      numeroDocumento: data['numero_documento']?.toString() ?? '',
      telefonoMovil: data['telefono_movil']?.toString() ?? '',
      correo: data['correo']?.toString() ?? '',
      direccion: data['direccion']?.toString() ?? '',
      distrito: data['distrito']?.toString() ?? '',
      provincia: data['provincia']?.toString() ?? '',
      departamento: data['departamento']?.toString() ?? '',
      referencia: data['referencia']?.toString() ?? '',
      seccion: data['seccion']?.toString() ?? '',
      seccionKey: data['seccion_key']?.toString() ?? sectionKeyFromData(data),
      campanaBanco: data['campana_banco']?.toString() ?? '',
      diasAtraso: (data['dias_atraso'] as num?)?.toInt() ?? 0,
      importeDeudaAsignada: (data['importe_deuda_asignada'] as num?)?.toDouble() ?? 0.0,
      importeDeudaPendiente: (data['importe_deuda_pendiente'] as num?)?.toDouble() ?? 0.0,
      estadoGestion: data['estado_gestion']?.toString() ?? 'pendiente',
      notaGestor: data['nota_gestor']?.toString() ?? '',
      tramoActual: (data['tramo_actual'] as num?)?.toInt() ?? 1,
      fechaGestion: data['fecha_gestion']?.toString() ?? '',
      coordenadaX: coords.x,
      coordenadaY: coords.y,
      ubicacionVerificadaLat: uv.lat,
      ubicacionVerificadaLng: uv.lng,
      ubicacionVerificadaGestor: uv.gestor,
      ubicacionVerificadaFecha: uv.fecha,
      cartasGestor: (data['cartas_gestor'] is List)
          ? (data['cartas_gestor'] as List)
              .asMap()
              .entries
              .map((entry) => CartaGenerada.fromMap(
                    'local_${entry.key}',
                    Map<String, dynamic>.from(entry.value as Map),
                  ))
              .toList()
          : const [],
      fechaPromesaPago: data['fecha_promesa_pago']?.toString() ?? '',
      montoPromesaPago: _toDouble(data['monto_promesa_pago']),
      nivel1: data['nivel_1']?.toString() ?? '',
      nivel2: data['nivel_2']?.toString() ?? '',
      nivel3: data['nivel_3']?.toString() ?? '',
      nivel4: data['nivel_4']?.toString() ?? '',
      canalGestion: data['canal_gestion']?.toString() ?? '',
      actualizadoPorUid: data['actualizado_por_uid']?.toString() ?? '',
      actualizadoPorNombre: data['actualizado_por_nombre']?.toString() ?? '',
      activoEnCartera: _parseActivoEnCartera(data),
      fechaAsignacion: data['fecha_asignacion']?.toString() ??
          data['fecha_asignacion_dt']?.toString() ??
          '',
      diaCiclo: (data['dia_ciclo'] as num?)?.toInt() ?? 1,
      estadoCiclo: data['estado_ciclo']?.toString() ?? 'activa',
      gestionEspecial: data['gestion_especial'] == true,
      motivoGestionEspecial:
          data['motivo_gestion_especial']?.toString() ?? '',
      etiquetas: _parseEtiquetas(data['etiquetas']),
    );
  }

  static String sectionKeyFromData(Map<String, dynamic> data) {
    final key = data['seccion_key']?.toString() ?? '';
    if (key.isNotEmpty) return key;
    return data['seccion']?.toString() ?? '';
  }

  String get displayName {
    if (nombreCompleto.isNotEmpty) return nombreCompleto;
    return '$nombres $apellidoPaterno $apellidoMaterno'.trim();
  }

  String get fullAddress {
    return [direccion, distrito, provincia, departamento]
        .where((s) => s.isNotEmpty)
        .join(', ');
  }

  bool get isHighValue => importeDeudaAsignada > 500;
  bool get isPendiente => estadoGestion == 'pendiente';
  bool get isDevolucionPendiente => estadoGestion == 'devolucion_pendiente';
  /// Active clients in gestor workload (excludes archived, closed cycle, returns).
  bool get isActiveForGestor =>
      activoEnCartera &&
      !isDevolucionPendiente &&
      estadoCiclo == 'activa';

  /// Etiqueta de ciclo: "Día X de 59 · Etapa N"
  String get cicloLabel {
    const duracion = 59;
    final etapa = tramoActual <= 0 ? 1 : tramoActual;
    return 'Día $diaCiclo de $duracion · Etapa $etapa';
  }

  bool get isGestionEspecialSection =>
      seccionKey == '_GESTION_ESPECIAL' || gestionEspecial;
  bool get isVisitado => estadoGestion != 'pendiente' && !isDevolucionPendiente;
  bool get hasPromesa =>
      montoPromesaPago > 0 || fechaPromesaPago.trim().isNotEmpty;

  /// Recuperación según datos del banco (asignada − pendiente).
  double get recuperadoBanco {
    final v = importeDeudaAsignada - importeDeudaPendiente;
    return v > 0 ? v : 0;
  }
  bool get hasPhone => telefonoMovil.trim().isNotEmpty;
  bool get hasCoordinates => coordenadaX != 0 && coordenadaY != 0;
  bool get hasVerifiedLocation =>
      ubicacionVerificadaLat != 0 && ubicacionVerificadaLng != 0;
  double get latitude => coordenadaY;
  double get longitude => coordenadaX;

  String get initials {
    final name = displayName;
    if (name.isEmpty) return '?';
    final words = name.split(' ').where((w) => w.isNotEmpty).toList();
    if (words.length >= 2) return '${words[0][0]}${words[1][0]}'.toUpperCase();
    return name[0].toUpperCase();
  }

  ClientModel copyWith({List<String>? etiquetas, int? cuentasMismoDni}) {
    return ClientModel(
      id: id,
      campaignId: campaignId,
      codigoCliente: codigoCliente,
      nombreCompleto: nombreCompleto,
      nombres: nombres,
      apellidoPaterno: apellidoPaterno,
      apellidoMaterno: apellidoMaterno,
      numeroDocumento: numeroDocumento,
      telefonoMovil: telefonoMovil,
      correo: correo,
      direccion: direccion,
      distrito: distrito,
      provincia: provincia,
      departamento: departamento,
      referencia: referencia,
      seccion: seccion,
      seccionKey: seccionKey,
      campanaBanco: campanaBanco,
      diasAtraso: diasAtraso,
      importeDeudaAsignada: importeDeudaAsignada,
      importeDeudaPendiente: importeDeudaPendiente,
      estadoGestion: estadoGestion,
      notaGestor: notaGestor,
      tramoActual: tramoActual,
      fechaGestion: fechaGestion,
      coordenadaX: coordenadaX,
      coordenadaY: coordenadaY,
      ubicacionVerificadaLat: ubicacionVerificadaLat,
      ubicacionVerificadaLng: ubicacionVerificadaLng,
      ubicacionVerificadaGestor: ubicacionVerificadaGestor,
      ubicacionVerificadaFecha: ubicacionVerificadaFecha,
      cartasGestor: cartasGestor,
      fechaPromesaPago: fechaPromesaPago,
      montoPromesaPago: montoPromesaPago,
      nivel1: nivel1,
      nivel2: nivel2,
      nivel3: nivel3,
      nivel4: nivel4,
      canalGestion: canalGestion,
      actualizadoPorUid: actualizadoPorUid,
      actualizadoPorNombre: actualizadoPorNombre,
      activoEnCartera: activoEnCartera,
      fechaAsignacion: fechaAsignacion,
      diaCiclo: diaCiclo,
      estadoCiclo: estadoCiclo,
      gestionEspecial: gestionEspecial,
      motivoGestionEspecial: motivoGestionEspecial,
      etiquetas: etiquetas ?? this.etiquetas,
      cuentasMismoDni: cuentasMismoDni ?? this.cuentasMismoDni,
    );
  }
}
