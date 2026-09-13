class CarteraJobError {
  final String code;
  final String message;

  const CarteraJobError({this.code = '', this.message = ''});

  factory CarteraJobError.fromMap(Map<String, dynamic>? data) {
    if (data == null) return const CarteraJobError();
    return CarteraJobError(
      code: data['code']?.toString() ?? '',
      message: data['message']?.toString() ?? '',
    );
  }

  bool get hasError => message.isNotEmpty || code.isNotEmpty;
}

class CarteraProgreso {
  final String paso;
  final int current;
  final int total;
  final String mensaje;

  const CarteraProgreso({
    this.paso = '',
    this.current = 0,
    this.total = 0,
    this.mensaje = '',
  });

  factory CarteraProgreso.fromMap(Map<String, dynamic>? data) {
    if (data == null) return const CarteraProgreso();
    return CarteraProgreso(
      paso: data['paso']?.toString() ?? '',
      current: (data['current'] as num?)?.toInt() ?? 0,
      total: (data['total'] as num?)?.toInt() ?? 0,
      mensaje: data['mensaje']?.toString() ?? '',
    );
  }

  double get fraction {
    if (total <= 0) return 0;
    return (current / total).clamp(0, 1);
  }
}

class CarteraResumen {
  final int totalClientes;
  final int totalSecciones;
  final double deudaAsignada;
  final double deudaPendiente;

  const CarteraResumen({
    this.totalClientes = 0,
    this.totalSecciones = 0,
    this.deudaAsignada = 0,
    this.deudaPendiente = 0,
  });

  factory CarteraResumen.fromMap(Map<String, dynamic>? data) {
    if (data == null) return const CarteraResumen();
    return CarteraResumen(
      totalClientes: (data['total_clientes'] as num?)?.toInt() ?? 0,
      totalSecciones: (data['total_secciones'] as num?)?.toInt() ?? 0,
      deudaAsignada: (data['total_deuda_asignada'] as num?)?.toDouble() ?? 0,
      deudaPendiente: (data['total_deuda_pendiente'] as num?)?.toDouble() ?? 0,
    );
  }
}

class CarteraDiff {
  final int nuevos;
  final int actualizados;
  final int removidos;
  final int sinCambios;
  final List<String> seccionesAfectadas;

  const CarteraDiff({
    this.nuevos = 0,
    this.actualizados = 0,
    this.removidos = 0,
    this.sinCambios = 0,
    this.seccionesAfectadas = const [],
  });

  factory CarteraDiff.fromMap(Map<String, dynamic>? data) {
    if (data == null) return const CarteraDiff();
    return CarteraDiff(
      nuevos: (data['nuevos'] as num?)?.toInt() ?? 0,
      actualizados: (data['actualizados'] as num?)?.toInt() ?? 0,
      removidos: (data['removidos'] as num?)?.toInt() ?? 0,
      sinCambios: (data['sin_cambios'] as num?)?.toInt() ?? 0,
      seccionesAfectadas: _stringList(data['secciones_afectadas']),
    );
  }
}

class CarteraMuestra {
  final String codigoCliente;
  final String nombreCompleto;
  final String seccionKey;

  const CarteraMuestra({
    this.codigoCliente = '',
    this.nombreCompleto = '',
    this.seccionKey = '',
  });

  factory CarteraMuestra.fromMap(Map<String, dynamic> data) {
    return CarteraMuestra(
      codigoCliente: data['codigo_cliente']?.toString() ?? '',
      nombreCompleto: data['nombre_completo']?.toString() ?? '',
      seccionKey: data['seccion_key']?.toString() ?? '',
    );
  }
}

class CarteraJob {
  final String id;
  final String estado;
  final String modo;
  final String campaignId;
  final String archivoNombre;
  final CarteraProgreso progreso;
  final CarteraResumen resumen;
  final CarteraDiff diff;
  final List<String> seccionesSinGestor;
  final List<CarteraMuestra> nuevos;
  final List<CarteraMuestra> removidos;
  final List<CarteraMuestra> actualizados;
  final CarteraJobError error;
  final DateTime? creadoAt;
  final String storagePath;
  final String parsedPath;

  const CarteraJob({
    required this.id,
    this.estado = '',
    this.modo = '',
    this.campaignId = 'cartera_activa',
    this.archivoNombre = '',
    this.progreso = const CarteraProgreso(),
    this.resumen = const CarteraResumen(),
    this.diff = const CarteraDiff(),
    this.seccionesSinGestor = const [],
    this.nuevos = const [],
    this.removidos = const [],
    this.actualizados = const [],
    this.error = const CarteraJobError(),
    this.creadoAt,
    this.storagePath = '',
    this.parsedPath = '',
  });

  bool get hasParsed => parsedPath.isNotEmpty;

  factory CarteraJob.fromMap(String id, Map<String, dynamic> data) {
    final archivo = _asStringKeyedMap(data['archivo']);
    final muestras = _asStringKeyedMap(data['muestras']);
    return CarteraJob(
      id: id,
      estado: data['estado']?.toString() ?? '',
      modo: data['modo']?.toString() ?? '',
      campaignId: data['campaign_id']?.toString() ?? 'cartera_activa',
      archivoNombre: archivo['nombre']?.toString() ?? '',
      progreso: CarteraProgreso.fromMap(_asStringKeyedMap(data['progreso'])),
      resumen: CarteraResumen.fromMap(_asStringKeyedMap(data['resumen'])),
      diff: CarteraDiff.fromMap(_asStringKeyedMap(data['diff'])),
      seccionesSinGestor: _stringList(data['secciones_sin_gestor']),
      nuevos: _muestraList(muestras['nuevos']),
      removidos: _muestraList(muestras['removidos']),
      actualizados: _muestraList(muestras['actualizados']),
      error: CarteraJobError.fromMap(_asStringKeyedMap(data['error'])),
      creadoAt: _asDateTime(data['creado_at']),
      storagePath: archivo['storage_path']?.toString() ?? '',
      parsedPath: archivo['parsed_path']?.toString() ?? '',
    );
  }
}

Map<String, dynamic> _asStringKeyedMap(dynamic raw) {
  if (raw is Map<String, dynamic>) return raw;
  if (raw is Map) {
    return raw.map((key, value) => MapEntry(key.toString(), value));
  }
  return {};
}

List<String> _stringList(dynamic raw) {
  if (raw is! List) return const [];
  return raw.map((e) => e.toString()).where((e) => e.isNotEmpty).toList();
}

List<CarteraMuestra> _muestraList(dynamic raw) {
  if (raw is! List) return const [];
  return raw
      .map((e) => CarteraMuestra.fromMap(_asStringKeyedMap(e)))
      .toList();
}

DateTime? _asDateTime(dynamic raw) {
  if (raw == null) return null;
  if (raw is DateTime) return raw;
  try {
    final converted = raw.toDate();
    if (converted is DateTime) return converted;
  } catch (_) {}
  return DateTime.tryParse(raw.toString());
}
