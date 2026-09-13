/// Plantilla de mensaje WhatsApp (empresa o personal).
class WhatsAppPlantilla {
  final String id;
  final String nombre;
  final String cuerpo;
  final bool activa;
  final int orden;
  final bool predeterminada;
  /// `personal` | `empresa`
  final String origen;

  const WhatsAppPlantilla({
    required this.id,
    required this.nombre,
    required this.cuerpo,
    this.activa = true,
    this.orden = 0,
    this.predeterminada = false,
    this.origen = 'personal',
  });

  bool get isEmpresa => origen == 'empresa';
  bool get isPersonal => origen == 'personal';

  factory WhatsAppPlantilla.fromMap(
    String id,
    Map<String, dynamic> data, {
    String origen = 'personal',
  }) {
    return WhatsAppPlantilla(
      id: id,
      nombre: data['nombre']?.toString() ?? '',
      cuerpo: data['cuerpo']?.toString() ?? '',
      activa: data['activa'] != false,
      orden: (data['orden'] as num?)?.toInt() ?? 0,
      predeterminada: data['predeterminada'] == true,
      origen: origen,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'nombre': nombre,
      'cuerpo': cuerpo,
      'activa': activa,
      'orden': orden,
      'predeterminada': predeterminada,
    };
  }

  WhatsAppPlantilla copyWith({
    String? id,
    String? nombre,
    String? cuerpo,
    bool? activa,
    int? orden,
    bool? predeterminada,
    String? origen,
  }) {
    return WhatsAppPlantilla(
      id: id ?? this.id,
      nombre: nombre ?? this.nombre,
      cuerpo: cuerpo ?? this.cuerpo,
      activa: activa ?? this.activa,
      orden: orden ?? this.orden,
      predeterminada: predeterminada ?? this.predeterminada,
      origen: origen ?? this.origen,
    );
  }
}

/// Variables disponibles para insertar en el editor.
const whatsappPlantillaVariables = <String>[
  'nombre',
  'dni',
  'codigo',
  'deuda',
  'dias_atraso',
  'tramo',
  'direccion',
  'distrito',
  'telefono',
  'gestor',
];
