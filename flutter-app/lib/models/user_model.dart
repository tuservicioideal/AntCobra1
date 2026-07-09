/// User profile model matching the Firestore 'usuarios' collection.
class UserModel {
  final String uid;
  final String nombre;
  final String email;
  final String seccion;
  final List<String> secciones;
  final String rol;
  final String telefono;
  final String zona;
  final String region;
  final String canal;
  final bool activo;

  UserModel({
    required this.uid,
    this.nombre = '',
    this.email = '',
    this.seccion = '',
    this.secciones = const [],
    this.rol = 'gestor',
    this.telefono = '',
    this.zona = '',
    this.region = '',
    this.canal = 'campo',
    this.activo = true,
  });

  factory UserModel.fromMap(String uid, Map<String, dynamic> data) {
    // Parse secciones array; fall back to empty list
    final rawSecciones = data['secciones'];
    final List<String> parsedSecciones = (rawSecciones is List)
        ? rawSecciones.map((e) => e.toString()).toList()
        : <String>[];

    return UserModel(
      uid: uid,
      nombre: data['nombre']?.toString() ?? '',
      email: data['email']?.toString() ?? '',
      seccion: data['seccion']?.toString() ?? '',
      secciones: parsedSecciones,
      rol: data['rol']?.toString() ?? 'gestor',
      telefono: data['telefono']?.toString() ?? '',
      zona: data['zona']?.toString() ?? '',
      region: data['region']?.toString() ?? '',
      canal: data['canal']?.toString() ?? 'campo',
      activo: _parseBool(data['activo'], defaultValue: true),
    );
  }

  static bool _parseBool(dynamic value, {required bool defaultValue}) {
    if (value == null) return defaultValue;
    if (value is bool) return value;
    if (value is num) return value != 0;
    if (value is String) {
      final normalized = value.toLowerCase().trim();
      if (normalized == 'true' || normalized == '1' || normalized == 'si' || normalized == 'sí') {
        return true;
      }
      if (normalized == 'false' || normalized == '0' || normalized == 'no') {
        return false;
      }
    }
    return defaultValue;
  }

  Map<String, dynamic> toMap() {
    return {
      'nombre': nombre,
      'email': email,
      'seccion': seccion,
      'secciones': secciones,
      'rol': rol,
      'telefono': telefono,
      'zona': zona,
      'region': region,
      'canal': canal,
      'activo': activo,
    };
  }

  bool get isAdmin => rol == 'admin';
  bool get isSupervisor => rol == 'supervisor';
  bool get isAsistente => rol == 'asistente';
  bool get isGestor => rol == 'gestor';
  bool get isCallGestor => isGestor && canal == 'call';
  bool get isFieldGestor => isGestor && canal != 'call';
  bool get canManageUsers => isAdmin || isSupervisor;
  bool get canViewStats => isAdmin || isSupervisor || isAsistente;
  bool get canViewDashboard => true; // All roles

  String get initials {
    if (nombre.isEmpty) return '?';
    final words = nombre.split(' ').where((w) => w.isNotEmpty).toList();
    if (words.length >= 2) return '${words[0][0]}${words[1][0]}'.toUpperCase();
    return nombre[0].toUpperCase();
  }

  UserModel copyWith({
    String? uid,
    String? nombre,
    String? email,
    String? seccion,
    List<String>? secciones,
    String? rol,
    String? telefono,
    String? zona,
    String? region,
    String? canal,
    bool? activo,
  }) {
    return UserModel(
      uid: uid ?? this.uid,
      nombre: nombre ?? this.nombre,
      email: email ?? this.email,
      seccion: seccion ?? this.seccion,
      secciones: secciones ?? this.secciones,
      rol: rol ?? this.rol,
      telefono: telefono ?? this.telefono,
      zona: zona ?? this.zona,
      region: region ?? this.region,
      canal: canal ?? this.canal,
      activo: activo ?? this.activo,
    );
  }
}
