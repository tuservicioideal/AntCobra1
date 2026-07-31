import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../services/auth_service.dart';
import '../../services/doxeo_queue_service.dart';

/// Sección "Doxeo" de la ficha del cliente: encola consultas Telegram en la
/// cola Firestore (las ejecuta cualquier PC con twi abierto), muestra el
/// resultado en vivo y el historial de consultas del cliente.
class ClientDetailDoxeoSection extends StatefulWidget {
  final ClientModel client;

  const ClientDetailDoxeoSection({super.key, required this.client});

  @override
  State<ClientDetailDoxeoSection> createState() =>
      _ClientDetailDoxeoSectionState();
}

class _ClientDetailDoxeoSectionState extends State<ClientDetailDoxeoSection> {
  final _queue = DoxeoQueueService();

  String _selectedComandoId = '';
  String? _activeJobId;
  bool _launching = false;

  String get _dni => widget.client.numeroDocumento.trim();
  String get _clienteId =>
      widget.client.id.isNotEmpty ? widget.client.id : widget.client.codigoCliente;

  Future<void> _launch(List<DoxeoComando> comandos) async {
    final profile = context.read<AuthService>().profile;
    if (profile == null) return;
    DoxeoComando? comando;
    for (final c in comandos) {
      if (c.id == _selectedComandoId) comando = c;
    }
    setState(() => _launching = true);
    try {
      final yaActiva = await _queue.tieneConsultaActiva(
        uid: profile.uid,
        clienteId: _clienteId,
      );
      if (yaActiva) {
        _showSnack('Ya tienes una consulta en curso para este cliente.',
            isError: true);
        return;
      }
      final jobId = await _queue.crearConsulta(
        cliente: widget.client,
        solicitante: profile,
        comando: comando,
      );
      if (!mounted) return;
      setState(() => _activeJobId = jobId);
    } catch (e) {
      _showSnack('No se pudo encolar la consulta: $e', isError: true);
    } finally {
      if (mounted) setState(() => _launching = false);
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? AppTheme.danger : AppTheme.success,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.travel_explore,
                    size: 18, color: AppTheme.primaryColor),
                const SizedBox(width: 8),
                Text(
                  'Doxeo · Telegram',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: Colors.grey.shade800,
                  ),
                ),
                const Spacer(),
                DoxeoWorkersBadge(queue: _queue),
              ],
            ),
            const SizedBox(height: 10),
            if (_dni.isEmpty)
              Text(
                'Este cliente no tiene DNI registrado; no se puede consultar.',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              )
            else ...[
              _buildComandoPicker(),
              const SizedBox(height: 10),
              _buildActiveJob(),
            ],
            const SizedBox(height: 6),
            _buildHistorial(),
          ],
        ),
      ),
    );
  }

  Widget _buildComandoPicker() {
    return StreamBuilder<List<DoxeoComando>>(
      stream: _queue.streamComandos(),
      builder: (context, snap) {
        final comandos = snap.data ?? const <DoxeoComando>[];
        DoxeoComando? seleccionado;
        for (final c in comandos) {
          if (c.id == _selectedComandoId) {
            seleccionado = c;
            break;
          }
        }
        final preview = seleccionado?.previewMessage(_dni) ?? _dni;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                ChoiceChip(
                  label: const Text('Solo DNI', style: TextStyle(fontSize: 11)),
                  selected: _selectedComandoId.isEmpty,
                  onSelected: (_) =>
                      setState(() => _selectedComandoId = ''),
                ),
                ...comandos.map(
                  (c) => ChoiceChip(
                    label: Text(c.nombre, style: const TextStyle(fontSize: 11)),
                    selected: _selectedComandoId == c.id,
                    onSelected: (_) =>
                        setState(() => _selectedComandoId = c.id),
                  ),
                ),
              ],
            ),
            if (comandos.isEmpty && snap.connectionState == ConnectionState.active)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  'Aún no hay comandos creados en el panel (se sincronizan solos).',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                ),
              ),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.primaryLight,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                'Se enviará: $preview',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primaryDark,
                ),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed:
                    _launching || _activeJobId != null ? null : () => _launch(comandos),
                icon: _launching
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.send, size: 16),
                label: Text(_launching ? 'Encolando…' : 'Consultar'),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildActiveJob() {
    final jobId = _activeJobId;
    if (jobId == null) return const SizedBox.shrink();
    return StreamBuilder<DoxeoJob>(
      stream: _queue.streamJob(jobId),
      builder: (context, snap) {
        final job = snap.data;
        if (job == null) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          );
        }
        return DoxeoJobView(
          job: job,
          queue: _queue,
          onCancel: job.isPending
              ? () async {
                  await _queue.cancelarJob(job.id);
                }
              : null,
          onClose: job.isDone
              ? () => setState(() => _activeJobId = null)
              : null,
        );
      },
    );
  }

  Widget _buildHistorial() {
    if (_clienteId.isEmpty) return const SizedBox.shrink();
    return StreamBuilder<List<DoxeoJob>>(
      stream: _queue.streamHistorialCliente(_clienteId),
      builder: (context, snap) {
        final jobs = (snap.data ?? const <DoxeoJob>[])
            .where((j) => j.id != _activeJobId)
            .toList();
        if (jobs.isEmpty) return const SizedBox.shrink();
        return ExpansionTile(
          tilePadding: EdgeInsets.zero,
          childrenPadding: EdgeInsets.zero,
          title: Text(
            'Historial de consultas (${jobs.length})',
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          ),
          children: jobs
              .map((job) => _HistorialTile(job: job, queue: _queue))
              .toList(),
        );
      },
    );
  }
}

/// Badge con el número de PCs con twi abierto (heartbeat reciente).
class DoxeoWorkersBadge extends StatelessWidget {
  final DoxeoQueueService queue;

  const DoxeoWorkersBadge({super.key, required this.queue});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<DoxeoWorker>>(
      stream: queue.streamWorkers(),
      builder: (context, snap) {
        final workers = (snap.data ?? const <DoxeoWorker>[])
            .where((w) => w.online)
            .toList();
        final conTelegram = workers.where((w) => w.telegramOk).length;
        final Color color;
        final IconData icon;
        final String text;
        if (workers.isEmpty) {
          color = AppTheme.danger;
          icon = Icons.cloud_off;
          text = 'Sin PCs conectadas';
        } else if (conTelegram == 0) {
          color = AppTheme.warning;
          icon = Icons.warning_amber_rounded;
          text = '${workers.length} PC(s) sin sesión Telegram';
        } else {
          color = AppTheme.success;
          icon = Icons.cloud_done_outlined;
          text = '$conTelegram PC(s) listas';
        }
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: color.withValues(alpha: 0.3)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 13, color: color),
              const SizedBox(width: 4),
              Text(text, style: TextStyle(fontSize: 10, color: color)),
            ],
          ),
        );
      },
    );
  }
}

class _HistorialTile extends StatelessWidget {
  final DoxeoJob job;
  final DoxeoQueueService queue;

  const _HistorialTile({required this.job, required this.queue});

  @override
  Widget build(BuildContext context) {
    final fecha = job.creadoAt;
    final fechaTexto = fecha == null
        ? ''
        : '${fecha.day.toString().padLeft(2, '0')}/${fecha.month.toString().padLeft(2, '0')} '
            '${fecha.hour.toString().padLeft(2, '0')}:${fecha.minute.toString().padLeft(2, '0')}';
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      dense: true,
      leading: DoxeoJobStatusDot(estado: job.estado),
      title: Text(
        job.comandoNombre.isEmpty ? 'Solo DNI' : job.comandoNombre,
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
      ),
      subtitle: Text(
        '$fechaTexto · DNI ${job.dni}',
        style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
      ),
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: DoxeoJobView(job: job, queue: queue, compact: true),
        ),
      ],
    );
  }
}

/// Punto de color según el estado del job.
class DoxeoJobStatusDot extends StatelessWidget {
  final String estado;

  const DoxeoJobStatusDot({super.key, required this.estado});

  static Color colorFor(String estado) {
    switch (estado) {
      case 'completado':
        return AppTheme.success;
      case 'timeout':
        return AppTheme.warning;
      case 'error':
        return AppTheme.danger;
      case 'en_proceso':
        return AppTheme.info;
      case 'cancelado':
        return AppTheme.textMuted;
      default:
        return AppTheme.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 10,
      height: 10,
      decoration:
          BoxDecoration(color: colorFor(estado), shape: BoxShape.circle),
    );
  }
}

/// Vista de un job: progreso (pendiente/en proceso) o resultado final.
/// Reutilizada por la ficha del cliente y por la pantalla Consultas.
class DoxeoJobView extends StatelessWidget {
  final DoxeoJob job;
  final DoxeoQueueService queue;
  final VoidCallback? onCancel;
  final VoidCallback? onClose;
  final bool compact;

  const DoxeoJobView({
    super.key,
    required this.job,
    required this.queue,
    this.onCancel,
    this.onClose,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.divider,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _statusChip(),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  job.mensaje.isEmpty ? job.dni : 'Enviado: ${job.mensaje}',
                  style: const TextStyle(
                      fontSize: 11, color: AppTheme.textSecondary),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (onClose != null)
                InkWell(
                  onTap: onClose,
                  child: const Icon(Icons.close,
                      size: 16, color: AppTheme.textMuted),
                ),
            ],
          ),
          const SizedBox(height: 8),
          if (job.isPending || job.isRunning) _buildProgress(),
          if (job.estado == 'cancelado')
            const Text('Consulta cancelada.',
                style: TextStyle(fontSize: 12, color: AppTheme.textMuted)),
          if (job.estado == 'timeout')
            _banner(AppTheme.warning,
                job.errorMsg.isEmpty ? 'El bot no respondió a tiempo.' : job.errorMsg),
          if (job.estado == 'error')
            _banner(AppTheme.danger,
                job.errorMsg.isEmpty ? 'Error ejecutando la consulta.' : job.errorMsg),
          if (job.estado == 'completado') _buildResult(context),
        ],
      ),
    );
  }

  Widget _statusChip() {
    final color = DoxeoJobStatusDot.colorFor(job.estado);
    final label = switch (job.estado) {
      'pendiente' => 'En cola',
      'en_proceso' => 'Ejecutando',
      'completado' => 'Completado',
      'timeout' => 'Sin respuesta',
      'error' => 'Error',
      'cancelado' => 'Cancelado',
      _ => job.estado,
    };
    return Chip(
      avatar: Icon(Icons.circle, size: 10, color: color),
      label: Text(label, style: TextStyle(fontSize: 10, color: color)),
      visualDensity: VisualDensity.compact,
      side: BorderSide(color: color.withValues(alpha: 0.4)),
      padding: EdgeInsets.zero,
    );
  }

  Widget _buildProgress() {
    return Row(
      children: [
        const SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            job.isPending
                ? 'Esperando que una PC con el sistema lo tome…'
                : 'Lo está ejecutando ${job.workerId} (hasta 1 min)…',
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
        ),
        if (onCancel != null)
          TextButton(
            onPressed: onCancel,
            child: const Text('Cancelar', style: TextStyle(fontSize: 12)),
          ),
      ],
    );
  }

  Widget _banner(Color color, String text) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.info_outline, size: 15, color: color),
        const SizedBox(width: 6),
        Expanded(child: Text(text, style: TextStyle(fontSize: 12, color: color))),
      ],
    );
  }

  Widget _buildResult(BuildContext context) {
    final tieneDatos = job.hasData;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (!tieneDatos)
          const Text(
            'El bot respondió pero sin datos útiles para este DNI.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
        if (job.nombre.isNotEmpty) ...[
          const Text('Nombre',
              style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
          SelectableText(
            job.nombre,
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
          ),
          const SizedBox(height: 8),
        ],
        if (job.phones.isNotEmpty) ...[
          const Text('Teléfonos',
              style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: job.phones
                .map((p) => ActionChip(
                      avatar: const Icon(Icons.phone, size: 13),
                      label: Text(p, style: const TextStyle(fontSize: 11)),
                      visualDensity: VisualDensity.compact,
                      onPressed: () => _showPhoneActions(context, p),
                    ))
                .toList(),
          ),
          const SizedBox(height: 8),
        ],
        if (job.addresses.isNotEmpty) ...[
          const Text('Direcciones',
              style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
          ...job.addresses.map(
            (a) => Padding(
              padding: const EdgeInsets.only(top: 2),
              child: SelectableText('• $a',
                  style: const TextStyle(fontSize: 12)),
            ),
          ),
        ],
        if (job.ubicacionTexto.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              job.ubicacionTexto,
              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
          ),
        if (job.imagenes.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('Imágenes',
              style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: job.imagenes
                .map((path) => _StorageImageThumb(path: path, queue: queue))
                .toList(),
          ),
        ],
        if (job.raw.isNotEmpty && !compact) ...[
          const SizedBox(height: 6),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Respuesta completa',
                style: TextStyle(fontSize: 12)),
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: SelectableText(job.raw,
                    style: const TextStyle(fontSize: 11)),
              ),
            ],
          ),
        ],
      ],
    );
  }

  void _showPhoneActions(BuildContext context, String phone) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.phone),
              title: Text('Llamar a $phone'),
              onTap: () {
                Navigator.pop(ctx);
                launchUrl(Uri.parse('tel:$phone'));
              },
            ),
            ListTile(
              leading: const Icon(Icons.copy),
              title: const Text('Copiar número'),
              onTap: () {
                Clipboard.setData(ClipboardData(text: phone));
                Navigator.pop(ctx);
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// Miniatura de imagen del worker (Storage) con vista ampliada al tocar.
class _StorageImageThumb extends StatelessWidget {
  final String path;
  final DoxeoQueueService queue;

  const _StorageImageThumb({required this.path, required this.queue});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: queue.resolveImageUrl(path),
      builder: (context, snap) {
        final url = snap.data;
        if (url == null) {
          return Container(
            width: 96,
            height: 96,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          );
        }
        return GestureDetector(
          onTap: () => showDialog(
            context: context,
            builder: (ctx) => Dialog(
              insetPadding: const EdgeInsets.all(12),
              child: InteractiveViewer(
                child: Image.network(url, fit: BoxFit.contain),
              ),
            ),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.network(
              url,
              width: 96,
              height: 96,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Container(
                width: 96,
                height: 96,
                color: AppTheme.surface,
                child: const Icon(Icons.broken_image_outlined,
                    color: AppTheme.textMuted),
              ),
            ),
          ),
        );
      },
    );
  }
}
