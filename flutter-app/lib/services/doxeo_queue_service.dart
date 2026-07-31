import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';

import '../models/client_model.dart';
import '../models/user_model.dart';

/// Comando Doxeo espejado desde el panel twi (colección `doxeo_comandos`).
/// La plantilla puede incluir `{dni}`; si no, se antepone al DNI.
class DoxeoComando {
  final String id;
  final String nombre;
  final String plantilla;
  final String descripcion;
  final String chatRef;
  final bool activo;
  final int orden;

  const DoxeoComando({
    required this.id,
    required this.nombre,
    this.plantilla = '',
    this.descripcion = '',
    this.chatRef = '',
    this.activo = true,
    this.orden = 0,
  });

  factory DoxeoComando.fromMap(String id, Map<String, dynamic> data) {
    return DoxeoComando(
      id: id,
      nombre: data['nombre']?.toString() ?? '',
      plantilla: data['plantilla']?.toString() ?? '',
      descripcion: data['descripcion']?.toString() ?? '',
      chatRef: data['chat_ref']?.toString() ?? '',
      activo: data['activo'] != false,
      orden: (data['orden'] as num?)?.toInt() ?? 0,
    );
  }

  /// Vista previa del mensaje que el worker enviará a Telegram.
  String previewMessage(String dni) {
    final tpl = plantilla.trim();
    if (tpl.isEmpty) return dni;
    if (tpl.contains('{dni}')) return tpl.replaceAll('{dni}', dni).trim();
    return '$tpl $dni'.trim();
  }
}

/// Heartbeat de una PC con twi abierto (colección `doxeo_workers`).
class DoxeoWorker {
  final String id;
  final bool telegramOk;
  final DateTime? ultimoSeen;

  const DoxeoWorker({required this.id, this.telegramOk = false, this.ultimoSeen});

  factory DoxeoWorker.fromMap(String id, Map<String, dynamic> data) {
    return DoxeoWorker(
      id: id,
      telegramOk: data['telegram_ok'] == true,
      ultimoSeen: (data['ultimo_seen'] as Timestamp?)?.toDate(),
    );
  }

  /// Se considera conectada si el heartbeat tiene menos de 90 s.
  bool get online {
    final seen = ultimoSeen;
    if (seen == null) return false;
    return DateTime.now().difference(seen).inSeconds < 90;
  }
}

/// Trabajo de consulta encolado (colección `doxeo_jobs`).
class DoxeoJob {
  final String id;
  final String dni;
  final String comandoId;
  final String comandoNombre;
  final String mensaje;
  final String estado;
  final String workerId;
  final String errorMsg;
  final DateTime? creadoAt;
  final Map<String, dynamic> parsed;
  final String raw;
  final List<String> imagenes;
  final bool hasData;

  const DoxeoJob({
    required this.id,
    this.dni = '',
    this.comandoId = '',
    this.comandoNombre = '',
    this.mensaje = '',
    this.estado = 'pendiente',
    this.workerId = '',
    this.errorMsg = '',
    this.creadoAt,
    this.parsed = const {},
    this.raw = '',
    this.imagenes = const [],
    this.hasData = false,
  });

  factory DoxeoJob.fromMap(String id, Map<String, dynamic> data) {
    final resultado = data['resultado'];
    final resultadoMap = resultado is Map<String, dynamic> ? resultado : null;
    final parsedRaw = resultadoMap?['parsed'];
    final imagenesRaw = resultadoMap?['imagenes'];
    return DoxeoJob(
      id: id,
      dni: data['dni']?.toString() ?? '',
      comandoId: data['comando_id']?.toString() ?? '',
      comandoNombre: data['comando_nombre']?.toString() ?? '',
      mensaje: data['mensaje']?.toString() ?? '',
      estado: data['estado']?.toString() ?? 'pendiente',
      workerId: data['worker_id']?.toString() ?? '',
      errorMsg: data['error_msg']?.toString() ?? '',
      creadoAt: (data['creado_at'] as Timestamp?)?.toDate(),
      parsed: parsedRaw is Map<String, dynamic> ? parsedRaw : const {},
      raw: resultadoMap?['raw']?.toString() ?? '',
      imagenes: imagenesRaw is List
          ? imagenesRaw.map((e) => e.toString()).toList()
          : const [],
      hasData: resultadoMap?['has_data'] == true,
    );
  }

  bool get isPending => estado == 'pendiente';
  bool get isRunning => estado == 'en_proceso';
  bool get isDone =>
      estado == 'completado' || estado == 'timeout' || estado == 'error' || estado == 'cancelado';

  String get nombre => parsed['nombre']?.toString() ?? '';

  List<String> get phones => parsed['phones'] is List
      ? (parsed['phones'] as List).map((e) => e.toString()).toList()
      : const [];

  List<String> get addresses => parsed['addresses'] is List
      ? (parsed['addresses'] as List).map((e) => e.toString()).toList()
      : const [];

  String get ubicacionTexto => [
        parsed['distrito']?.toString() ?? '',
        parsed['provincia']?.toString() ?? '',
        parsed['departamento']?.toString() ?? '',
      ].where((s) => s.isNotEmpty).join(', ');
}

/// Cola Doxeo vía Firestore: el APK encola el trabajo y cualquier PC con
/// twi abierto lo reclama y ejecuta contra el bot de Telegram.
class DoxeoQueueService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  /// Comandos activos creados en el panel twi (ordenados por el panel).
  Stream<List<DoxeoComando>> streamComandos() {
    return _db.collection('doxeo_comandos').snapshots().map((snap) {
      final comandos = snap.docs
          .map((doc) => DoxeoComando.fromMap(doc.id, doc.data()))
          .where((c) => c.activo)
          .toList();
      comandos.sort((a, b) {
        final byOrden = a.orden.compareTo(b.orden);
        if (byOrden != 0) return byOrden;
        return a.nombre.toLowerCase().compareTo(b.nombre.toLowerCase());
      });
      return comandos;
    });
  }

  /// PCs con twi abierto (heartbeat reciente = conectada).
  Stream<List<DoxeoWorker>> streamWorkers() {
    return _db.collection('doxeo_workers').snapshots().map((snap) {
      return snap.docs.map((doc) => DoxeoWorker.fromMap(doc.id, doc.data())).toList();
    });
  }

  Stream<DoxeoJob> streamJob(String jobId) {
    return _db
        .collection('doxeo_jobs')
        .doc(jobId)
        .snapshots()
        .map((doc) => DoxeoJob.fromMap(doc.id, doc.data() ?? const {}));
  }

  /// Últimas consultas hechas sobre un cliente (historial de la ficha).
  Stream<List<DoxeoJob>> streamHistorialCliente(String clienteId, {int limit = 10}) {
    return _db
        .collection('doxeo_jobs')
        .where('cliente.cliente_id', isEqualTo: clienteId)
        .orderBy('creado_at', descending: true)
        .limit(limit)
        .snapshots()
        .map((snap) =>
            snap.docs.map((doc) => DoxeoJob.fromMap(doc.id, doc.data())).toList());
  }

  /// Últimas consultas lanzadas por el gestor (pantalla Consultas).
  Stream<List<DoxeoJob>> streamHistorialGestor(String uid, {int limit = 15}) {
    return _db
        .collection('doxeo_jobs')
        .where('solicitante.uid', isEqualTo: uid)
        .orderBy('creado_at', descending: true)
        .limit(limit)
        .snapshots()
        .map((snap) =>
            snap.docs.map((doc) => DoxeoJob.fromMap(doc.id, doc.data())).toList());
  }

  /// Anti-abuso: no encolar si el mismo gestor ya tiene una consulta viva
  /// (pendiente o en proceso) sobre el mismo cliente.
  Future<bool> tieneConsultaActiva({required String uid, required String clienteId}) async {
    final snap = await _db
        .collection('doxeo_jobs')
        .where('cliente.cliente_id', isEqualTo: clienteId)
        .orderBy('creado_at', descending: true)
        .limit(10)
        .get();
    for (final doc in snap.docs) {
      final data = doc.data();
      final estado = data['estado']?.toString() ?? '';
      final solicitante = data['solicitante'];
      final solicitanteUid =
          solicitante is Map ? solicitante['uid']?.toString() ?? '' : '';
      if (solicitanteUid == uid &&
          (estado == 'pendiente' || estado == 'en_proceso')) {
        return true;
      }
    }
    return false;
  }

  /// Encola la consulta. Devuelve el id del job para escucharlo con
  /// [streamJob]. `comando` nulo = "Solo DNI".
  Future<String> crearConsulta({
    required ClientModel cliente,
    required UserModel solicitante,
    DoxeoComando? comando,
    String? dniOverride,
  }) async {
    final dni = (dniOverride ?? cliente.numeroDocumento).trim();
    if (dni.length < 7) {
      throw ArgumentError('DNI inválido para la consulta Doxeo.');
    }
    final clienteId = cliente.id.isNotEmpty ? cliente.id : cliente.codigoCliente;
    final mensaje = comando?.previewMessage(dni) ?? dni;
    final doc = await _db.collection('doxeo_jobs').add({
      'dni': dni,
      'comando_id': comando?.id ?? '',
      'comando_nombre': comando?.nombre ?? 'Solo DNI',
      'mensaje': mensaje,
      'cliente': {
        'campaign_id': cliente.campaignId,
        'seccion_key': cliente.seccionKey,
        'cliente_id': clienteId,
        'nombre': cliente.displayName,
      },
      'solicitante': {
        'uid': solicitante.uid,
        'nombre': solicitante.nombre,
        'email': solicitante.email,
      },
      'estado': 'pendiente',
      'intentos': 0,
      'creado_at': FieldValue.serverTimestamp(),
    });
    return doc.id;
  }

  /// Cancelación mientras siga pendiente (reglas: solo el solicitante).
  Future<void> cancelarJob(String jobId) {
    return _db.collection('doxeo_jobs').doc(jobId).update({'estado': 'cancelado'});
  }

  /// URL temporal de una imagen subida por el worker a Storage.
  Future<String> resolveImageUrl(String storagePath) {
    return FirebaseStorage.instance.ref(storagePath).getDownloadURL();
  }
}
