import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/cartera_job_model.dart';
import '../services/auth_service.dart';
import '../services/cartera_upload_service.dart';
import '../utils/cartera_upload_logic.dart';
import '../utils/responsive.dart';
import '../utils/stats_format.dart';
import '../widgets/stat_card.dart';

class CarteraUploadScreen extends StatefulWidget {
  const CarteraUploadScreen({super.key});

  @override
  State<CarteraUploadScreen> createState() => _CarteraUploadScreenState();
}

class _CarteraUploadScreenState extends State<CarteraUploadScreen> {
  final _service = CarteraUploadService();

  bool _busy = false;
  bool _forceSinGestor = false;
  String? _jobId;
  CarteraJob? _job;
  String? _localError;
  List<CarteraJob> _recent = const [];

  @override
  void initState() {
    super.initState();
    _loadRecent();
  }

  Future<void> _loadRecent() async {
    try {
      final jobs = await _service.listRecentJobs();
      if (!mounted) return;
      setState(() => _recent = jobs);
    } catch (e) {
      debugPrint('listRecentJobs: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    if (!auth.canManageUsers) {
      return Scaffold(
        appBar: AppBar(title: const Text('Cargar cartera')),
        body: const Center(
          child: Text('Solo administradores o supervisores pueden cargar cartera.'),
        ),
      );
    }

    final blocking = _busy ||
        _job?.estado == 'parseando' ||
        _job?.estado == 'publicando' ||
        _job?.estado == 'subiendo';

    return PopScope(
      canPop: !blocking,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final ok = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Salir de la carga'),
            content: const Text(
              'Hay una carga en curso. Si sales, el trabajo sigue en el servidor. ¿Salir igual?',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Seguir aquí'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Salir'),
              ),
            ],
          ),
        );
        if (ok == true && context.mounted) Navigator.pop(context);
      },
      child: Scaffold(
      appBar: AppBar(title: const Text('Cargar cartera del banco')),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: ResponsiveBreakpoints.contentMax),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                'Sube el Excel del banco. Los gestores verán la cartera en el APK '
                'después de confirmar. Las visitas ya registradas se conservan.',
                style: TextStyle(color: Colors.grey.shade700, height: 1.35),
              ),
              if (!kIsWeb) ...[
                const SizedBox(height: 12),
                _banner(
                  AppTheme.warningLight,
                  AppTheme.warning,
                  'En el celular conviene un archivo chico. Para la cartera completa usa la web en una PC.',
                ),
              ],
              const SizedBox(height: 16),
              if (_localError != null) ...[
                _banner(AppTheme.dangerLight, AppTheme.danger, _localError!),
                const SizedBox(height: 12),
              ],
              if (_jobId == null) ...[
                _buildPicker(),
                if (_recent.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  _buildHistory(),
                ],
              ] else
                _buildJobBody(),
            ],
          ),
        ),
      ),
    ),
    );
  }

  Widget _banner(Color bg, Color fg, String text) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: fg.withValues(alpha: 0.3)),
      ),
      child: Text(text, style: TextStyle(color: fg, height: 1.35)),
    );
  }

  Widget _buildPicker() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Archivo Excel',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
            ),
            const SizedBox(height: 8),
            Text(
              'Formato .xlsx del banco (columnas de región, zona, sección y código cliente).',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _busy ? null : _pickAndStart,
              icon: _busy
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.upload_file),
              label: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_busy ? 'Subiendo…' : 'Elegir Excel'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHistory() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Últimas cargas',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
            ),
            const SizedBox(height: 8),
            ..._recent.take(8).map((job) {
              return ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                title: Text(
                  job.archivoNombre.isEmpty ? job.id : job.archivoNombre,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                subtitle: Text(
                  '${jobEstadoLabel(job.estado)}'
                  '${job.creadoAt == null ? '' : ' · ${_fmtWhen(job.creadoAt!)}'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: _busy
                    ? null
                    : () => setState(() {
                          _jobId = job.id;
                          _job = job;
                          _localError = null;
                        }),
              );
            }),
          ],
        ),
      ),
    );
  }

  String _fmtWhen(DateTime dt) {
    final local = dt.toLocal();
    final y = local.year.toString().padLeft(4, '0');
    final m = local.month.toString().padLeft(2, '0');
    final d = local.day.toString().padLeft(2, '0');
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '$d/$m/$y $hh:$mm';
  }

  Widget _buildJobBody() {
    return StreamBuilder<CarteraJob>(
      stream: _service.watchJob(_jobId!),
      builder: (context, snap) {
        final job = snap.data ?? _job;
        if (job == null) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 32),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        _job = job;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _statusCard(job),
            const SizedBox(height: 12),
            if (job.estado == 'preview' ||
                job.estado == 'publicando' ||
                job.estado == 'listo')
              _preview(job),
            if (job.estado == 'error' && job.error.hasError) ...[
              const SizedBox(height: 12),
              _banner(AppTheme.dangerLight, AppTheme.danger, job.error.message),
            ],
            const SizedBox(height: 16),
            _actions(job),
          ],
        );
      },
    );
  }

  Widget _statusCard(CarteraJob job) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Chip(label: Text(jobEstadoLabel(job.estado))),
                if (job.archivoNombre.isNotEmpty)
                  Text(
                    job.archivoNombre,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
              ],
            ),
            if (job.progreso.mensaje.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(job.progreso.mensaje, style: TextStyle(color: Colors.grey.shade700)),
            ],
            if (job.estado == 'parseando' ||
                job.estado == 'publicando' ||
                job.estado == 'subiendo') ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: job.progreso.total > 0 ? job.progreso.fraction : null,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _preview(CarteraJob job) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 700;
            final cards = [
              StatCard(
                label: 'Clientes',
                value: '${job.resumen.totalClientes}',
                icon: Icons.people_outline,
                color: AppTheme.primary,
              ),
              StatCard(
                label: 'Secciones',
                value: '${job.resumen.totalSecciones}',
                icon: Icons.grid_view,
                color: AppTheme.info,
              ),
              StatCard(
                label: 'Deuda asignada',
                value: formatMoneyCompact(job.resumen.deudaAsignada),
                icon: Icons.payments_outlined,
                color: AppTheme.accent,
              ),
              StatCard(
                label: 'Nuevos / bajas',
                value: '${job.diff.nuevos} / ${job.diff.removidos}',
                icon: Icons.sync_alt,
                color: AppTheme.warning,
              ),
            ];
            if (wide) {
              return Row(
                children: [
                  for (var i = 0; i < cards.length; i++) ...[
                    if (i > 0) const SizedBox(width: 8),
                    Expanded(child: cards[i]),
                  ],
                ],
              );
            }
            return GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 1.6,
              children: cards,
            );
          },
        ),
        if (job.seccionesSinGestor.isNotEmpty) ...[
          const SizedBox(height: 12),
          _banner(
            AppTheme.warningLight,
            AppTheme.warning,
            'Secciones sin gestor: ${job.seccionesSinGestor.join(', ')}. '
            'Asígnalas en Administración o confirma publicar igual.',
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _forceSinGestor,
            onChanged: _busy
                ? null
                : (v) => setState(() => _forceSinGestor = v ?? false),
            title: const Text('Publicar igual (los clientes quedan en Firestore)'),
            controlAffinity: ListTileControlAffinity.leading,
          ),
        ],
        if (job.nuevos.isNotEmpty) _sampleBlock('Altas (muestra)', job.nuevos),
        if (job.removidos.isNotEmpty) _sampleBlock('Bajas (muestra)', job.removidos),
        if (job.actualizados.isNotEmpty)
          _sampleBlock('Actualizados (muestra)', job.actualizados),
      ],
    );
  }

  Widget _sampleBlock(String title, List<CarteraMuestra> items) {
    return Card(
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ...items.take(8).map(
              (e) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(
                  '${e.codigoCliente}  ·  ${e.nombreCompleto}  ·  ${e.seccionKey}',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _actions(CarteraJob job) {
    final canPublish = canConfirmPublish(
      estado: job.estado,
      totalClientes: job.resumen.totalClientes,
      seccionesSinGestor: job.seccionesSinGestor,
      forceSinGestor: _forceSinGestor,
    );
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        if (canPublish)
          FilledButton.icon(
            onPressed: _busy ? null : () => _publish(job.id),
            icon: const Icon(Icons.cloud_upload_outlined),
            label: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Confirmar y publicar'),
            ),
          ),
        if (job.estado == 'error' && job.hasParsed)
          FilledButton.icon(
            onPressed: _busy ? null : () => _publish(job.id),
            icon: const Icon(Icons.refresh),
            label: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Reintentar publicar'),
            ),
          ),
        if (job.estado == 'error' && !job.hasParsed && job.storagePath.isNotEmpty)
          OutlinedButton(
            onPressed: _busy ? null : () => _retryParse(job.id),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Reintentar parse'),
            ),
          ),
        if (job.estado == 'error' || job.estado == 'listo')
          OutlinedButton(
            onPressed: _busy
                ? null
                : () {
                    setState(() {
                      _jobId = null;
                      _job = null;
                      _localError = null;
                      _forceSinGestor = false;
                    });
                    _loadRecent();
                  },
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Cargar otro Excel'),
            ),
          ),
      ],
    );
  }

  Future<void> _pickAndStart() async {
    setState(() {
      _localError = null;
      _busy = true;
    });
    try {
      final picked = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['xlsx', 'xlsm'],
        withData: true,
        allowMultiple: false,
      );
      if (picked == null || picked.files.isEmpty) {
        return;
      }
      final file = picked.files.single;
      final nameError = validateExcelFileName(file.name);
      if (nameError != null) {
        setState(() => _localError = nameError);
        return;
      }
      final bytes = file.bytes;
      if (bytes == null) {
        setState(() => _localError = 'No se pudo leer el archivo. Prueba en la web.');
        return;
      }
      if (exceedsMaxExcelSize(bytes.length)) {
        setState(() => _localError = 'El archivo supera 50 MB.');
        return;
      }
      if (shouldWarnLargeFile(isWeb: kIsWeb, bytes: bytes.length)) {
        final ok = await _confirmLargeFile();
        if (ok != true) return;
      }
      final jobId = await _service.uploadAndCreateJob(
        bytes: bytes,
        filename: file.name,
      );
      if (!mounted) return;
      setState(() => _jobId = jobId);
      await _service.parseJob(jobId);
      await _loadRecent();
    } catch (e) {
      if (!mounted) return;
      setState(() => _localError = _service.mapError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool?> _confirmLargeFile() {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Archivo grande'),
        content: const Text(
          'Este Excel es pesado para un celular. ¿Quieres continuar o mejor subirlo desde la web?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Continuar'),
          ),
        ],
      ),
    );
  }

  Future<void> _retryParse(String jobId) async {
    setState(() {
      _busy = true;
      _localError = null;
    });
    try {
      await _service.parseJob(jobId);
      await _loadRecent();
    } catch (e) {
      if (!mounted) return;
      setState(() => _localError = _service.mapError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _publish(String jobId) async {
    setState(() {
      _busy = true;
      _localError = null;
    });
    try {
      await _service.publishJob(jobId);
    } catch (e) {
      if (!mounted) return;
      setState(() => _localError = _service.mapError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}
