import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../../config/theme.dart';
import '../../models/descargo_model.dart';
import '../../services/auth_service.dart';
import '../../services/descargo_service.dart';

/// Sección "Descargos y evidencias" de la ficha del cliente.
///
/// El gestor registra lo que respondió la persona contactada
/// ("no soy el titular", "no lo conozco", etc.) con foto y/o audio
/// como respaldo de la gestión.
class ClientDetailDescargoSection extends StatelessWidget {
  final String campaignId;
  final String section;
  final String clientId;
  final double? currentLat;
  final double? currentLng;
  final bool readOnly;

  const ClientDetailDescargoSection({
    super.key,
    required this.campaignId,
    required this.section,
    required this.clientId,
    this.currentLat,
    this.currentLng,
    this.readOnly = false,
  });

  @override
  Widget build(BuildContext context) {
    final service = DescargoService();
    return StreamBuilder<List<DescargoModel>>(
      stream: service.streamDescargos(
        campaignId: campaignId,
        section: section,
        clientId: clientId,
      ),
      builder: (context, snap) {
        if (snap.hasError) {
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.record_voice_over_outlined,
                          size: 18, color: AppTheme.primaryColor),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Descargos y evidencias',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.red.shade200),
                    ),
                    child: Text(
                      'No se pudieron cargar los descargos. Revisa tu conexión.',
                      style: TextStyle(
                          fontSize: 12, color: Colors.red.shade700),
                    ),
                  ),
                ],
              ),
            ),
          );
        }
        final items = snap.data ?? const <DescargoModel>[];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.record_voice_over_outlined,
                        size: 18, color: AppTheme.primaryColor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Descargos y evidencias (${items.length})',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                          color: Colors.grey.shade800,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (!readOnly)
                      FilledButton.icon(
                        onPressed: () => _openAddSheet(context, service),
                        icon: const Icon(Icons.add, size: 16),
                        label: const Text('Agregar',
                            style: TextStyle(fontSize: 12)),
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 8),
                          minimumSize: Size.zero,
                          tapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Lo que dijo la persona contactada. Respalda tu gestión.',
                  style:
                      TextStyle(fontSize: 11, color: Colors.grey.shade600),
                ),
                const SizedBox(height: 10),
                if (snap.connectionState == ConnectionState.waiting)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                else if (items.isEmpty)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey.shade50,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.grey.shade200),
                    ),
                    child: Text(
                      'Sin descargos. Si alguien dice “no soy la persona” o “no la conozco”, regístralo aquí con foto o audio.',
                      style: TextStyle(
                          fontSize: 12, color: Colors.grey.shade600),
                    ),
                  )
                else
                  ...items.map((d) => _DescargoTile(descargo: d)),
              ],
            ),
          ),
        );
      },
    );
  }

  void _openAddSheet(BuildContext context, DescargoService service) {
    final auth = context.read<AuthService>();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(ctx).viewInsets.bottom,
        ),
        child: _AddDescargoSheet(
          service: service,
          campaignId: campaignId,
          section: section,
          clientId: clientId,
          currentLat: currentLat,
          currentLng: currentLng,
          gestorNombre: auth.profile?.nombre ?? '',
        ),
      ),
    );
  }
}

class _DescargoTile extends StatelessWidget {
  final DescargoModel descargo;

  const _DescargoTile({required this.descargo});

  @override
  Widget build(BuildContext context) {
    final color = DescargoTipos.color(descargo.tipoRespuesta);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                  border:
                      Border.all(color: color.withValues(alpha: 0.35)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(DescargoTipos.icon(descargo.tipoRespuesta),
                        size: 13, color: color),
                    const SizedBox(width: 4),
                    Text(
                      DescargoTipos.label(descargo.tipoRespuesta),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: color,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Text(
                descargo.fechaFormatted,
                style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
              ),
            ],
          ),
          if (descargo.gestorNombre.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                descargo.gestorNombre,
                style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
              ),
            ),
          if (descargo.texto.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                descargo.texto,
                style: const TextStyle(fontSize: 12, height: 1.35),
              ),
            ),
          if (descargo.evidencias.isNotEmpty) ...[
            const SizedBox(height: 8),
            _EvidenciasRow(evidencias: descargo.evidencias),
          ],
          if (descargo.hasGps)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(
                children: [
                  Icon(Icons.location_on_outlined,
                      size: 12, color: Colors.grey.shade500),
                  const SizedBox(width: 4),
                  Text(
                    '${descargo.gpsLat.toStringAsFixed(5)}, ${descargo.gpsLng.toStringAsFixed(5)}',
                    style: TextStyle(
                        fontSize: 10, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _EvidenciasRow extends StatelessWidget {
  final List<DescargoEvidencia> evidencias;

  const _EvidenciasRow({required this.evidencias});

  @override
  Widget build(BuildContext context) {
    final fotos = evidencias.where((e) => e.isFoto).toList();
    final audios = evidencias.where((e) => e.isAudio).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (fotos.isNotEmpty)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: fotos
                .map((f) => _FotoThumb(evidencia: f))
                .toList(),
          ),
        if (fotos.isNotEmpty && audios.isNotEmpty)
          const SizedBox(height: 8),
        ...audios.map((a) => _AudioRow(evidencia: a)),
      ],
    );
  }
}

class _FotoThumb extends StatelessWidget {
  final DescargoEvidencia evidencia;

  const _FotoThumb({required this.evidencia});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => showDialog(
        context: context,
        builder: (ctx) => Dialog(
          insetPadding: const EdgeInsets.all(12),
          child: InteractiveViewer(
            child: Image.network(
              evidencia.downloadUrl,
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => const Padding(
                padding: EdgeInsets.all(24),
                child: Icon(Icons.broken_image_outlined),
              ),
            ),
          ),
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.network(
          evidencia.downloadUrl,
          width: 72,
          height: 72,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => Container(
            width: 72,
            height: 72,
            color: Colors.grey.shade200,
            child: const Icon(Icons.broken_image_outlined,
                color: Colors.grey),
          ),
        ),
      ),
    );
  }
}

class _AudioRow extends StatefulWidget {
  final DescargoEvidencia evidencia;

  const _AudioRow({required this.evidencia});

  @override
  State<_AudioRow> createState() => _AudioRowState();
}

class _AudioRowState extends State<_AudioRow> {
  AudioPlayer? _player;
  bool _playing = false;

  @override
  void dispose() {
    _player?.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_playing) {
      await _player?.stop();
      if (mounted) setState(() => _playing = false);
      return;
    }
    _player ??= AudioPlayer();
    try {
      await _player!.stop();
      await _player!.play(UrlSource(widget.evidencia.downloadUrl));
      if (mounted) setState(() => _playing = true);
      _player!.onPlayerComplete.first.then((_) {
        if (mounted) setState(() => _playing = false);
      });
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No se pudo reproducir el audio.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.primaryLight,
        borderRadius: BorderRadius.circular(10),
        border:
            Border.all(color: AppTheme.primary.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          InkWell(
            onTap: _toggle,
            borderRadius: BorderRadius.circular(20),
            child: Container(
              width: 32,
              height: 32,
              decoration: const BoxDecoration(
                color: AppTheme.primary,
                shape: BoxShape.circle,
              ),
              child: Icon(
                _playing ? Icons.stop : Icons.play_arrow,
                color: Colors.white,
                size: 18,
              ),
            ),
          ),
          const SizedBox(width: 8),
          const Expanded(
            child: Text('Audio de la respuesta',
                style: TextStyle(fontSize: 12)),
          ),
          Icon(Icons.mic_outlined, size: 14, color: Colors.grey.shade600),
        ],
      ),
    );
  }
}

/// Hoja para registrar un descargo con foto y/o audio.
class _AddDescargoSheet extends StatefulWidget {
  final DescargoService service;
  final String campaignId;
  final String section;
  final String clientId;
  final double? currentLat;
  final double? currentLng;
  final String gestorNombre;

  const _AddDescargoSheet({
    required this.service,
    required this.campaignId,
    required this.section,
    required this.clientId,
    this.currentLat,
    this.currentLng,
    this.gestorNombre = '',
  });

  @override
  State<_AddDescargoSheet> createState() => _AddDescargoSheetState();
}

class _AddDescargoSheetState extends State<_AddDescargoSheet> {
  final _textoController = TextEditingController();
  final _picker = ImagePicker();
  String _tipo = DescargoTipos.noEsTitular;
  final List<PendingEvidencia> _adjuntos = [];
  bool _saving = false;
  String? _textoError;

  // Grabación de audio
  final _recorder = AudioRecorder();
  bool _recording = false;
  int _recordSecs = 0;
  Timer? _recordTimer;
  String? _recordingPath;

  // Reproducción local antes de guardar
  AudioPlayer? _previewPlayer;
  String? _playingLocalPath;

  @override
  void dispose() {
    _textoController.dispose();
    _recordTimer?.cancel();
    _recorder.dispose();
    _previewPlayer?.dispose();
    super.dispose();
  }

  int get _fotoCount => _adjuntos.where((e) => e.tipo != 'audio').length;
  int get _audioCount => _adjuntos.where((e) => e.tipo == 'audio').length;

  void _snack(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: error ? Colors.red.shade600 : null,
      ),
    );
  }

  Future<void> _pickFoto(ImageSource source) async {
    if (_fotoCount >= DescargoService.maxFotos) {
      _snack('Máximo ${DescargoService.maxFotos} fotos.', error: true);
      return;
    }
    // En web el navegador pide el permiso; permission_handler no aplica.
    if (!kIsWeb) {
      final camPerm = await Permission.camera.request();
      if (source == ImageSource.camera && !camPerm.isGranted) {
        _snack('Permiso de cámara denegado.', error: true);
        return;
      }
    }
    try {
      final picked = await _picker.pickImage(
        source: source,
        imageQuality: 70,
        maxWidth: 1280,
      );
      if (picked == null) return;
      if (!mounted) return;
      // En web no hay ruta de archivo: se guarda el contenido en memoria
      // para subirlo con putData (FilePicker.path también es null en web).
      final bytes = kIsWeb ? await picked.readAsBytes() : null;
      setState(() => _adjuntos.add(PendingEvidencia(
            tipo: 'foto',
            localPath: kIsWeb ? '' : picked.path,
            mimeType: 'image/jpeg',
            bytes: bytes,
            fileName: picked.name,
          )));
    } catch (e) {
      _snack('No se pudo obtener la foto: $e', error: true);
    }
  }

  Future<void> _pickAudioFile() async {
    if (_audioCount >= DescargoService.maxAudios) {
      _snack('Máximo ${DescargoService.maxAudios} audios.', error: true);
      return;
    }
    try {
      final res = await FilePicker.platform.pickFiles(
        type: FileType.audio,
        allowMultiple: false,
        // Necesario en web: sin esto `bytes` es null y `path` siempre es null.
        withData: true,
      );
      if (res == null || res.files.isEmpty) return;
      final f = res.files.single;
      // En web `f.path` lanza UnsupportedError: no tocarlo.
      final path = kIsWeb ? '' : (f.path ?? '');
      final bytes = f.bytes;
      if (path.isEmpty && bytes == null) return;
      final mime = _guessAudioMime(f.name, path);
      if (!mounted) return;
      setState(() => _adjuntos.add(PendingEvidencia(
            tipo: 'audio',
            localPath: path,
            mimeType: mime,
            bytes: bytes,
            fileName: f.name,
          )));
    } catch (e) {
      _snack('No se pudo adjuntar el audio: $e', error: true);
    }
  }

  String _guessAudioMime(String name, String path) {
    final src = (name.isNotEmpty ? name : path).toLowerCase();
    if (src.endsWith('.wav')) return 'audio/wav';
    if (src.endsWith('.mp3')) return 'audio/mpeg';
    if (src.endsWith('.ogg') || src.endsWith('.oga')) return 'audio/ogg';
    if (src.endsWith('.mp4') || src.endsWith('.m4a')) return 'audio/m4a';
    if (src.endsWith('.aac')) return 'audio/aac';
    return 'audio/mpeg';
  }

  Future<void> _toggleRecording() async {
    if (_recording) {
      await _stopRecording(save: true);
      return;
    }
    // Grabación con `record` + subida por ruta solo está soportada en móvil.
    // En web se usa "Subir audio" (el navegador no expone archivo temporal).
    if (kIsWeb) {
      _snack('En web usa "Subir audio" para adjuntar.', error: true);
      return;
    }
    if (_audioCount >= DescargoService.maxAudios) {
      _snack('Máximo ${DescargoService.maxAudios} audios.', error: true);
      return;
    }
    final mic = await Permission.microphone.request();
    if (!mic.isGranted) {
      _snack('Permiso de micrófono denegado.', error: true);
      return;
    }
    try {
      final hasPerm = await _recorder.hasPermission();
      if (!hasPerm) {
        _snack('Sin permiso para grabar audio.', error: true);
        return;
      }
      final dir = await getTemporaryDirectory();
      final path =
          '${dir.path}/descargo_${DateTime.now().millisecondsSinceEpoch}.m4a';
      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.aacLc),
        path: path,
      );
      _recordingPath = path;
      if (!mounted) return;
      setState(() {
        _recording = true;
        _recordSecs = 0;
      });
      _recordTimer?.cancel();
      _recordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() => _recordSecs++);
      });
    } catch (e) {
      _snack('No se pudo iniciar la grabación: $e', error: true);
    }
  }

  Future<void> _stopRecording({required bool save}) async {
    _recordTimer?.cancel();
    try {
      final path = await _recorder.stop();
      final keep = save ? (path ?? _recordingPath) : null;
      if (!mounted) return;
      setState(() {
        _recording = false;
        _recordSecs = 0;
        _recordingPath = null;
      });
      if (save && keep != null && File(keep).existsSync()) {
        if (!mounted) return;
        final name = keep.split(RegExp(r'[/\\]')).last;
        setState(() => _adjuntos.add(PendingEvidencia(
              tipo: 'audio',
              localPath: keep,
              mimeType: 'audio/m4a',
              fileName: name,
            )));
      }
    } catch (e) {
      if (mounted) setState(() => _recording = false);
      _snack('Error al detener: $e', error: true);
    }
  }

  Future<void> _previewLocalAudio(PendingEvidencia adjunto, String key) async {
    if (_playingLocalPath == key) {
      await _previewPlayer?.stop();
      if (mounted) setState(() => _playingLocalPath = null);
      return;
    }
    _previewPlayer ??= AudioPlayer();
    try {
      await _previewPlayer!.stop();
      final Source source = adjunto.bytes != null
          ? BytesSource(adjunto.bytes!, mimeType: adjunto.mimeType)
          : DeviceFileSource(adjunto.localPath, mimeType: adjunto.mimeType);
      await _previewPlayer!.play(source);
      if (mounted) setState(() => _playingLocalPath = key);
      _previewPlayer!.onPlayerComplete.first.then((_) {
        if (mounted && _playingLocalPath == key) {
          setState(() => _playingLocalPath = null);
        }
      });
    } catch (_) {
      _snack('No se pudo reproducir.', error: true);
    }
  }

  String _friendlySaveError(Object e) {
    final raw = e.toString().replaceFirst('Bad state: ', '');
    final lower = raw.toLowerCase();
    if (lower.contains('al menos 10 caracteres')) return raw;
    if (lower.contains('permission-denied') ||
        lower.contains('unauthorized') ||
        lower.contains('sin permiso')) {
      return 'Sin permiso para registrar el descargo. Revisa tu sesión y que tengas la sección asignada.';
    }
    if (lower.contains('sin sesión') || lower.contains('unauthenticated')) {
      return 'Sesión vencida. Vuelve a iniciar sesión e intenta de nuevo.';
    }
    if (lower.contains('unavailable') ||
        lower.contains('network') ||
        lower.contains('timeout') ||
        lower.contains('sin conexión')) {
      return 'Sin conexión para guardar. Revisa internet e intenta de nuevo.';
    }
    if (lower.contains('supera 10 mb') || lower.contains('supera 5 mb')) {
      return raw;
    }
    return raw;
  }

  Future<void> _save() async {
    if (_saving) return;
    if (_recording) {
      _snack('Detén la grabación antes de guardar.', error: true);
      return;
    }
    // Validación local visible: antes solo fallaba en el servicio y el
    // error se mostraba como un snack fugaz → parecía que el botón no hacía nada.
    if (_textoController.text.trim().length < 10) {
      setState(() {
        _textoError =
            'Mínimo 10 caracteres (${_textoController.text.trim().length}/10).';
      });
      _snack('Describe el descargo con al menos 10 caracteres.', error: true);
      return;
    }
    // Capturar antes del await: tras Navigator.pop el context queda desactivado
    // y el SnackBar de éxito nunca se mostraba.
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final authUid = context.read<AuthService>().firebaseUser?.uid ?? '';
    setState(() => _saving = true);
    try {
      await widget.service.addDescargo(
        campaignId: widget.campaignId,
        section: widget.section,
        clientId: widget.clientId,
        tipoRespuesta: _tipo,
        texto: _textoController.text,
        evidencias: List.of(_adjuntos),
        lat: widget.currentLat,
        lng: widget.currentLng,
        gestorUid: authUid,
        gestorNombre: widget.gestorNombre,
      );
      if (!mounted) return;
      navigator.pop();
      messenger.showSnackBar(
        const SnackBar(content: Text('Descargo registrado.')),
      );
    } catch (e) {
      _snack(_friendlySaveError(e), error: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _fmtSecs(int s) =>
      '${(s ~/ 60).toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final fotos = _adjuntos.where((e) => e.tipo != 'audio').toList();
    final audios = _adjuntos.where((e) => e.tipo == 'audio').toList();
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Agregar descargo',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                  tooltip: 'Cerrar',
                ),
              ],
            ),
            Text(
              'Pide permiso antes de fotografiar o grabar. Describe con tus palabras lo que respondió.',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _tipo,
              decoration: const InputDecoration(
                labelText: '¿Qué respondió?',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              isExpanded: true,
              items: DescargoTipos.todos
                  .map((t) => DropdownMenuItem(
                        value: t,
                        child: Text(DescargoTipos.label(t),
                            style: const TextStyle(fontSize: 13)),
                      ))
                  .toList(),
              onChanged: (v) {
                if (v != null) setState(() => _tipo = v);
              },
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _textoController,
              maxLines: 4,
              maxLength: 1000,
              onChanged: (_) {
                if (_textoError != null &&
                    _textoController.text.trim().length >= 10) {
                  setState(() => _textoError = null);
                }
              },
              decoration: InputDecoration(
                labelText: 'Descargo (mín. 10 caracteres)',
                hintText:
                    'Ej. Atendió un hombre que dijo no ser el titular y no conocerlo…',
                border: const OutlineInputBorder(),
                isDense: true,
                errorText: _textoError,
              ),
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(Icons.photo_camera_outlined, size: 16),
                const SizedBox(width: 6),
                Text('Fotos (${fotos.length}/${DescargoService.maxFotos})',
                    style: const TextStyle(
                        fontSize: 12, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            if (fotos.isEmpty)
              Text('Sin fotos. Opcional, máx. ${DescargoService.maxFotos}.',
                  style:
                      TextStyle(fontSize: 11, color: Colors.grey.shade600)),
            if (fotos.isNotEmpty)
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: fotos.map((f) {
                  final hasBytes = f.bytes != null;
                  return Stack(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: hasBytes
                            ? Image.memory(
                                f.bytes!,
                                width: 72,
                                height: 72,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => Container(
                                  width: 72,
                                  height: 72,
                                  color: Colors.grey.shade200,
                                  child:
                                      const Icon(Icons.image_outlined),
                                ),
                              )
                            : Image.file(
                                File(f.localPath),
                                width: 72,
                                height: 72,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => Container(
                                  width: 72,
                                  height: 72,
                                  color: Colors.grey.shade200,
                                  child: const Icon(Icons.image_outlined),
                                ),
                              ),
                      ),
                      Positioned(
                        right: 0,
                        top: 0,
                        child: InkWell(
                          onTap: () =>
                              setState(() => _adjuntos.remove(f)),
                          child: Container(
                            decoration: const BoxDecoration(
                              color: Colors.black54,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.close,
                                size: 16, color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  );
                }).toList(),
              ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickFoto(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera, size: 16),
                    label: const Text('Cámara',
                        style: TextStyle(fontSize: 12)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickFoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined,
                        size: 16),
                    label: const Text('Galería',
                        style: TextStyle(fontSize: 12)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.mic_outlined, size: 16),
                const SizedBox(width: 6),
                Text(
                    'Audios (${audios.length}/${DescargoService.maxAudios})',
                    style: const TextStyle(
                        fontSize: 12, fontWeight: FontWeight.w600)),
                const Spacer(),
                if (_recording)
                  Text(_fmtSecs(_recordSecs),
                      style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: Colors.red.shade700)),
              ],
            ),
            const SizedBox(height: 8),
            ...audios.asMap().entries.map((entry) {
              final idx = entry.key;
              final a = entry.value;
              final name = a.displayName;
              final key = a.localPath.isNotEmpty
                  ? a.localPath
                  : 'bytes_${idx}_${a.displayName}_${a.bytes?.length ?? 0}';
              final playing = _playingLocalPath == key;
              return Container(
                margin: const EdgeInsets.only(bottom: 6),
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    InkWell(
                      onTap: () => _previewLocalAudio(a, key),
                      child: Icon(
                          playing ? Icons.stop_circle : Icons.play_circle,
                          size: 28,
                          color: AppTheme.primary),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 11)),
                    ),
                    InkWell(
                      onTap: () async {
                        await _previewPlayer?.stop();
                        if (mounted) {
                          setState(() {
                            _adjuntos.remove(a);
                            _playingLocalPath = null;
                          });
                        }
                      },
                      child: const Icon(Icons.delete_outline,
                          size: 18, color: Colors.red),
                    ),
                  ],
                ),
              );
            }),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _toggleRecording,
                    icon: Icon(
                      _recording ? Icons.stop : Icons.fiber_manual_record,
                      size: 16,
                      color: _recording ? Colors.white : Colors.red,
                    ),
                    label: Text(
                      _recording ? 'Detener' : 'Grabar',
                      style: const TextStyle(fontSize: 12),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          _recording ? Colors.red : Colors.white,
                      foregroundColor:
                          _recording ? Colors.white : Colors.black87,
                      side: BorderSide(
                          color: _recording
                              ? Colors.red
                              : Colors.grey.shade300),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickAudioFile,
                    icon: const Icon(Icons.upload_file, size: 16),
                    label: const Text('Subir audio',
                        style: TextStyle(fontSize: 12)),
                  ),
                ),
              ],
            ),
            if (kIsWeb)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  'En web la grabación directa está desactivada: usa "Subir audio".',
                  style:
                      TextStyle(fontSize: 11, color: Colors.grey.shade600),
                ),
              ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _saving ? null : _save,
                icon: _saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.save_outlined, size: 18),
                label: Text(_saving ? 'Guardando…' : 'Guardar descargo'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
