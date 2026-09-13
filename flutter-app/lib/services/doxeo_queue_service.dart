import 'dart:typed_data';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/foundation.dart';

import '../models/client_model.dart';
import '../models/user_model.dart';
import '../utils/file_output_helper.dart';
import '../utils/local_file_payload.dart';
import '../utils/open_local_file.dart';
import '../utils/stream_memo.dart';

const int doxeoMaxConcurrent = 1;
const int doxeoMaxPerHour = 30;
const int doxeoMaxPerDay = 80;

/// Un job pendiente/en_proceso más viejo que esto es huérfano (PC apagada a
/// mitad); no debe bloquear el cupo del gestor mientras el reaper lo expira.
const Duration doxeoJobVivoVentana = Duration(minutes: 15);

/// Quita el relleno de ceros que el Excel del banco aplica al documento
/// (`0047808409` → `47808409`). Solo quita ceros mientras sobren dígitos: un
/// DNI que legalmente empieza en 0 (`02820743`) queda intacto. Documentos
/// con letras u otros formatos se devuelven recortados, sin tocar.
String normalizarDocumento(String raw) {
  final limpio = raw.trim();
  if (limpio.isEmpty) return '';
  if (!RegExp(r'^[\d\s.\-]+$').hasMatch(limpio)) return limpio;
  var digitos = limpio.replaceAll(RegExp(r'\D'), '');
  while (digitos.length > 8 && digitos.startsWith('0')) {
    digitos = digitos.substring(1);
  }
  return digitos;
}

class DoxeoQuotaException implements Exception {
  final String message;
  const DoxeoQuotaException(this.message);

  @override
  String toString() => message;
}

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

/// Elige el comando a enviar. Sin selección válida usa el primero.
/// No existe la opción "Solo DNI": si no hay comandos, no se consulta.
DoxeoComando? resolverComando(List<DoxeoComando> comandos, String selectedId) {
  if (comandos.isEmpty) return null;
  for (final c in comandos) {
    if (c.id == selectedId) return c;
  }
  return comandos.first;
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

/// Adjunto no-imagen del resultado Doxeo (p. ej. PDF de Telegram).
class DoxeoArchivo {
  final String path;
  final String fileName;
  final String mimeType;

  const DoxeoArchivo({
    required this.path,
    this.fileName = '',
    this.mimeType = 'application/pdf',
  });

  factory DoxeoArchivo.fromMap(Map<String, dynamic> data) {
    final path = data['path']?.toString() ?? '';
    final name = data['file_name']?.toString() ?? '';
    final mime = data['mime_type']?.toString() ?? 'application/pdf';
    return DoxeoArchivo(
      path: path,
      fileName: name.isNotEmpty
          ? name
          : (path.isNotEmpty ? path.split('/').last : 'documento.pdf'),
      mimeType: mime.isNotEmpty ? mime : 'application/pdf',
    );
  }

  Map<String, dynamic> toMap() => {
        'path': path,
        'file_name': fileName,
        'mime_type': mimeType,
      };
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
  final List<DoxeoArchivo> archivos;
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
    this.archivos = const [],
    this.hasData = false,
  });

  factory DoxeoJob.fromMap(String id, Map<String, dynamic> data) {
    final resultado = data['resultado'];
    final resultadoMap = resultado is Map<String, dynamic> ? resultado : null;
    final parsedRaw = resultadoMap?['parsed'];
    final imagenesRaw = resultadoMap?['imagenes'];
    final archivosRaw = resultadoMap?['archivos'];
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
      archivos: _parseArchivos(archivosRaw),
      hasData: resultadoMap?['has_data'] == true,
    );
  }

  bool get isPending => estado == 'pendiente';
  bool get isRunning => estado == 'en_proceso';
  bool get isDone =>
      estado == 'completado' || estado == 'timeout' || estado == 'error' || estado == 'cancelado';

  bool get canRetry => estado == 'timeout' || estado == 'error';

  /// Hay algo útil para mostrar: texto OSINT, fotos o PDFs.
  bool get tieneContenidoUtil =>
      hasData || imagenes.isNotEmpty || archivos.isNotEmpty;

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

  factory DoxeoJob.fromConsultaGuardada(String key, Map<String, dynamic> data) {
    final resultado = data['resultado'];
    final resultadoMap =
        resultado is Map ? Map<String, dynamic>.from(resultado) : null;
    final parsedRaw = resultadoMap?['parsed'];
    final imagenesRaw = resultadoMap?['imagenes'];
    final archivosRaw = resultadoMap?['archivos'];
    DateTime? creadoAt;
    final actualizado = data['actualizado_at'];
    if (actualizado is Timestamp) {
      creadoAt = actualizado.toDate();
    } else if (actualizado is DateTime) {
      creadoAt = actualizado;
    }
    final comandoId =
        data['comando_id']?.toString() ?? (key == '_dni' ? '' : key);
    return DoxeoJob(
      id: data['job_id']?.toString() ?? key,
      dni: data['dni']?.toString() ?? '',
      comandoId: comandoId,
      comandoNombre: data['comando_nombre']?.toString() ?? '',
      mensaje: data['mensaje']?.toString() ?? '',
      estado: data['estado']?.toString() ?? 'completado',
      errorMsg: data['error_msg']?.toString() ?? '',
      creadoAt: creadoAt,
      parsed: parsedRaw is Map
          ? Map<String, dynamic>.from(parsedRaw)
          : const {},
      raw: resultadoMap?['raw']?.toString() ?? '',
      imagenes: imagenesRaw is List
          ? imagenesRaw.map((e) => e.toString()).toList()
          : const [],
      archivos: _parseArchivos(archivosRaw),
      hasData: resultadoMap?['has_data'] == true,
    );
  }

  Map<String, dynamic> toConsultaGuardadaMap() {
    return {
      'comando_id': comandoId,
      'comando_nombre': comandoNombre,
      'job_id': id,
      'estado': estado,
      'dni': dni,
      'mensaje': mensaje,
      'error_msg': errorMsg,
      'resultado': {
        'parsed': parsed,
        'raw': raw,
        'imagenes': imagenes,
        'archivos': archivos.map((a) => a.toMap()).toList(),
        'has_data': hasData,
      },
    };
  }
}

List<DoxeoArchivo> _parseArchivos(dynamic raw) {
  if (raw is! List) return const [];
  final out = <DoxeoArchivo>[];
  for (final item in raw) {
    if (item is Map) {
      final archivo = DoxeoArchivo.fromMap(Map<String, dynamic>.from(item));
      if (archivo.path.isNotEmpty) out.add(archivo);
    }
  }
  return out;
}

/// Clave del mapa `doxeo_consultas` en el documento del cliente.
/// Una consulta nueva del mismo tipo pisa la anterior.
String doxeoConsultaKey(String comandoId) {
  final key = comandoId.trim().replaceAll('.', '_');
  return key.isEmpty ? '_dni' : key;
}

bool debePersistirConsulta(String estado) {
  return estado == 'completado' || estado == 'timeout' || estado == 'error';
}

bool puedeGuardarConsultaEnCliente(ClientModel cliente) {
  final id = cliente.id.isNotEmpty ? cliente.id : cliente.codigoCliente;
  if (id.isEmpty || id.startsWith('libre_')) return false;
  return cliente.campaignId.isNotEmpty && cliente.seccionKey.isNotEmpty;
}

/// Conserva solo la consulta más reciente de cada tipo (comando).
List<DoxeoJob> ultimasConsultasPorTipo(Iterable<DoxeoJob> jobs) {
  final sorted = jobs.toList()
    ..sort((a, b) {
      final at = a.creadoAt;
      final bt = b.creadoAt;
      if (at == null && bt == null) return 0;
      if (at == null) return 1;
      if (bt == null) return -1;
      return bt.compareTo(at);
    });
  final seen = <String>{};
  final out = <DoxeoJob>[];
  for (final job in sorted) {
    if (seen.add(doxeoConsultaKey(job.comandoId))) {
      out.add(job);
    }
  }
  return out;
}

List<DoxeoJob> parseDoxeoConsultas(dynamic raw) {
  if (raw is! Map) return const [];
  final jobs = <DoxeoJob>[];
  raw.forEach((key, value) {
    if (value is Map) {
      jobs.add(DoxeoJob.fromConsultaGuardada(
        key.toString(),
        Map<String, dynamic>.from(value),
      ));
    }
  });
  return ultimasConsultasPorTipo(jobs);
}

/// Cola Doxeo vía Firestore: el APK encola el trabajo y cualquier PC con
/// twi abierto lo reclama y ejecuta contra el bot de Telegram.
class DoxeoQueueService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final _comandosMemo = StreamMemo<int, List<DoxeoComando>>();
  final _workersMemo = StreamMemo<int, List<DoxeoWorker>>();
  final _jobMemo = StreamMemo<String, DoxeoJob>();
  final _historialClienteMemo = StreamMemo<String, List<DoxeoJob>>();
  final _historialGestorMemo = StreamMemo<String, List<DoxeoJob>>();
  final _consultasClienteMemo = StreamMemo<String, List<DoxeoJob>>();

  /// Comandos activos creados en el panel twi (ordenados por el panel).
  Stream<List<DoxeoComando>> streamComandos() {
    return _comandosMemo.remember(0, () {
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
    });
  }

  /// PCs con twi abierto (heartbeat reciente = conectada).
  Stream<List<DoxeoWorker>> streamWorkers() {
    return _workersMemo.remember(0, () {
      return _db.collection('doxeo_workers').snapshots().map((snap) {
        return snap.docs
            .map((doc) => DoxeoWorker.fromMap(doc.id, doc.data()))
            .toList();
      });
    });
  }

  Stream<DoxeoJob> streamJob(String jobId) {
    return _jobMemo.remember(jobId, () {
      return _db
          .collection('doxeo_jobs')
          .doc(jobId)
          .snapshots()
          .map((doc) => DoxeoJob.fromMap(doc.id, doc.data() ?? const {}));
    });
  }

  /// Últimas consultas hechas sobre un cliente (historial de la ficha).
  Stream<List<DoxeoJob>> streamHistorialCliente(String clienteId, {int limit = 10}) {
    return _historialClienteMemo.remember('$clienteId:$limit', () {
      return _db
          .collection('doxeo_jobs')
          .where('cliente.cliente_id', isEqualTo: clienteId)
          .orderBy('creado_at', descending: true)
          .limit(limit)
          .snapshots()
          .map((snap) =>
              snap.docs.map((doc) => DoxeoJob.fromMap(doc.id, doc.data())).toList());
    });
  }

  /// Última consulta de cada tipo guardada en el documento del cliente.
  Stream<List<DoxeoJob>> streamConsultasCliente({
    required String campaignId,
    required String seccionKey,
    required String clienteId,
  }) {
    return _consultasClienteMemo.remember(
      '$campaignId/$seccionKey/$clienteId',
      () {
        return _db
            .collection('campañas')
            .doc(campaignId)
            .collection('gestores')
            .doc(seccionKey)
            .collection('clientes')
            .doc(clienteId)
            .snapshots()
            .map((doc) => parseDoxeoConsultas(doc.data()?['doxeo_consultas']));
      },
    );
  }

  /// Pisa `doxeo_consultas.{tipo}` en el cliente con el resultado más reciente.
  Future<void> guardarConsultaCliente({
    required ClientModel cliente,
    required DoxeoJob job,
  }) async {
    if (!debePersistirConsulta(job.estado)) return;
    if (!puedeGuardarConsultaEnCliente(cliente)) return;
    final clienteId =
        cliente.id.isNotEmpty ? cliente.id : cliente.codigoCliente;
    final key = doxeoConsultaKey(job.comandoId);
    final payload = job.toConsultaGuardadaMap()
      ..['actualizado_at'] = FieldValue.serverTimestamp();
    try {
      await _db
          .collection('campañas')
          .doc(cliente.campaignId)
          .collection('gestores')
          .doc(cliente.seccionKey)
          .collection('clientes')
          .doc(clienteId)
          .update({'doxeo_consultas.$key': payload});
    } catch (e) {
      debugPrint('No se pudo guardar la consulta Doxeo en el cliente: $e');
    }
  }

  /// Últimas consultas lanzadas por el gestor (pantalla Consultas).
  Stream<List<DoxeoJob>> streamHistorialGestor(String uid, {int limit = 15}) {
    return _historialGestorMemo.remember('$uid:$limit', () {
      return _db
          .collection('doxeo_jobs')
          .where('solicitante.uid', isEqualTo: uid)
          .orderBy('creado_at', descending: true)
          .limit(limit)
          .snapshots()
          .map((snap) =>
              snap.docs.map((doc) => DoxeoJob.fromMap(doc.id, doc.data())).toList());
    });
  }

  /// Cupo por gestor: 1 viva + topes por hora/día.
  Future<void> verificarCupo(String uid) async {
    final snap = await _db
        .collection('doxeo_jobs')
        .where('solicitante.uid', isEqualTo: uid)
        .orderBy('creado_at', descending: true)
        .limit(doxeoMaxPerDay)
        .get();
    final now = DateTime.now();
    final vivoDesde = now.subtract(doxeoJobVivoVentana);
    var concurrent = 0;
    var hour = 0;
    var day = 0;
    for (final doc in snap.docs) {
      final data = doc.data();
      final estado = data['estado']?.toString() ?? '';
      final creado = (data['creado_at'] as Timestamp?)?.toDate();
      if (estado == 'pendiente' || estado == 'en_proceso') {
        // Solo cuentan los jobs vivos: un huérfano viejo no puede dejar al
        // gestor sin poder consultar para siempre (bug 2026-09).
        if (creado != null && !creado.isAfter(vivoDesde)) continue;
        concurrent += 1;
      }
      if (creado == null) continue;
      if (now.difference(creado) <= const Duration(hours: 1)) hour += 1;
      if (now.difference(creado) <= const Duration(days: 1)) day += 1;
    }
    if (concurrent >= doxeoMaxConcurrent) {
      throw const DoxeoQuotaException(
        'Ya tienes una consulta en curso. Espera a que termine.',
      );
    }
    if (hour >= doxeoMaxPerHour) {
      throw DoxeoQuotaException(
        'Llegaste al tope de $doxeoMaxPerHour consultas por hora.',
      );
    }
    if (day >= doxeoMaxPerDay) {
      throw DoxeoQuotaException(
        'Llegaste al tope de $doxeoMaxPerDay consultas por día.',
      );
    }
  }

  /// Encola la consulta. Devuelve el id del job para escucharlo con
  /// [streamJob]. Requiere un comando del panel (DNI, seeker, árbol, etc.).
  Future<String> crearConsulta({
    required ClientModel cliente,
    required UserModel solicitante,
    required DoxeoComando comando,
    String? dniOverride,
  }) async {
    final dniOriginal = (dniOverride ?? cliente.numeroDocumento).trim();
    // La cartera llega del banco con ceros de relleno (0047808409); a
    // Telegram debe ir SIEMPRE el documento limpio.
    final dni = normalizarDocumento(dniOriginal);
    if (dni.length < 7) {
      throw ArgumentError('DNI inválido para la consulta Doxeo.');
    }
    await verificarCupo(solicitante.uid);
    final clienteId = cliente.id.isNotEmpty ? cliente.id : cliente.codigoCliente;
    final mensaje = comando.previewMessage(dni);
    final doc = await _db.collection('doxeo_jobs').add({
      'dni': dni,
      if (dniOriginal != dni) 'dni_original': dniOriginal,
      'comando_id': comando.id,
      'comando_nombre': comando.nombre,
      'mensaje': mensaje,
      'chat_ref': comando.chatRef,
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

  /// Descarga un PDF de Storage y lo abre con el visor del dispositivo.
  Future<void> openArchivo(DoxeoArchivo archivo) async {
    if (archivo.path.isEmpty) {
      throw StateError('El archivo no tiene ruta de almacenamiento.');
    }
    final bytes = await FirebaseStorage.instance
        .ref(archivo.path)
        .getData(10 * 1024 * 1024);
    if (bytes == null || bytes.isEmpty) {
      throw StateError('No se pudo descargar el PDF.');
    }
    final fileName =
        archivo.fileName.isNotEmpty ? archivo.fileName : 'documento.pdf';
    final payload = await writeBytesToDocuments(
      bytes: Uint8List.fromList(bytes),
      filename: fileName,
      subfolder: 'doxeo_pdfs',
    );
    await openLocalFile(
      LocalFilePayload(
        bytes: payload.bytes,
        name: payload.name,
        path: payload.path,
        mimeType: archivo.mimeType.isNotEmpty
            ? archivo.mimeType
            : 'application/pdf',
      ),
    );
  }
}
