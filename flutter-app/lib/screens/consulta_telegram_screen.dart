import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../services/auth_service.dart';
import '../services/campaign_service.dart';
import '../services/campaign_stats_service.dart';
import '../services/doxeo_queue_service.dart';
import '../utils/contact_metrics_utils.dart';
import '../widgets/client_detail/client_detail_doxeo_section.dart';

/// Pantalla "Consultas Telegram": elige cliente → elige consulta (comando) →
/// encola el trabajo en Firestore; cualquier PC con twi abierto lo ejecuta
/// contra el bot de Telegram y el resultado llega en vivo.
class ConsultaTelegramScreen extends StatefulWidget {
  final ClientModel? initialClient;
  final String? campaignId;

  const ConsultaTelegramScreen({super.key, this.initialClient, this.campaignId});

  @override
  State<ConsultaTelegramScreen> createState() => _ConsultaTelegramScreenState();
}

class _ConsultaTelegramScreenState extends State<ConsultaTelegramScreen> {
  final _queue = DoxeoQueueService();
  final _campaignService = CampaignService();
  final _statsService = CampaignStatsService();
  final _searchController = TextEditingController();
  final _dniController = TextEditingController();

  String _selectedCommandId = '';

  String? _campaignId;
  List<ClientModel> _allClients = [];
  bool _loadingClients = false;
  bool _clientsLoadedOnce = false;
  ClientModel? _selectedClient;
  Timer? _debounce;

  bool _launching = false;
  String? _activeJobId;

  @override
  void initState() {
    super.initState();
    _selectedClient = widget.initialClient;
    _campaignId = widget.campaignId;
    if (_selectedClient != null) {
      _dniController.text = _selectedClient!.numeroDocumento;
      unawaited(_ensureClientsLoaded());
    }
    _searchController.addListener(_onSearchChanged);
    _dniController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _dniController.dispose();
    super.dispose();
  }

  Future<void> _ensureClientsLoaded() async {
    if (_clientsLoadedOnce || _loadingClients) return;
    final campaignId = _campaignId ?? await _campaignService.getActiveCampaignId();
    if (campaignId == null) return;
    setState(() => _loadingClients = true);
    final clients = await _statsService.loadActiveClients(campaignId: campaignId);
    if (!mounted) return;
    setState(() {
      _campaignId = campaignId;
      _allClients = clients;
      _loadingClients = false;
      _clientsLoadedOnce = true;
    });
  }

  void _onSearchChanged() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      if (!mounted) return;
      final q = _searchController.text.trim();
      if (q.length >= 2 && !_clientsLoadedOnce) {
        await _ensureClientsLoaded();
      }
      if (mounted) setState(() {});
    });
  }

  List<ClientModel> get _clientMatches {
    final q = _searchController.text.trim();
    if (q.length < 2) return const [];
    return _allClients.where((c) => clientMatchesSearchQuery(c, q)).take(8).toList();
  }

  void _selectClient(ClientModel client) {
    setState(() {
      _selectedClient = client;
      _dniController.text = client.numeroDocumento;
      _searchController.clear();
    });
  }

  String get _dni => _dniController.text.replaceAll(RegExp(r'[^0-9A-Za-z]'), '');

  bool get _canQuery => !_launching && _activeJobId == null && _dni.length >= 7;

  Future<void> _runQuery(List<DoxeoComando> comandos) async {
    final profile = context.read<AuthService>().profile;
    if (profile == null) return;
    DoxeoComando? comando;
    for (final c in comandos) {
      if (c.id == _selectedCommandId) comando = c;
    }
    setState(() => _launching = true);
    try {
      final cliente = _selectedClient ??
          ClientModel(
            id: 'libre_${_dniController.text.trim()}',
            numeroDocumento: _dni,
            nombreCompleto: 'Consulta libre',
            campaignId: _campaignId ?? '',
          );
      final yaActiva = await _queue.tieneConsultaActiva(
        uid: profile.uid,
        clienteId: cliente.id,
      );
      if (yaActiva) {
        _showSnack('Ya tienes una consulta en curso para este cliente.',
            isError: true);
        return;
      }
      final jobId = await _queue.crearConsulta(
        cliente: cliente,
        solicitante: profile,
        comando: comando,
        dniOverride: _dni,
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
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Consulta Telegram'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(child: DoxeoWorkersBadge(queue: _queue)),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildWorkersBanner(),
          const SizedBox(height: 12),
          _buildClientCard(),
          const SizedBox(height: 12),
          _buildQueryCard(),
          const SizedBox(height: 16),
          _buildQueryButton(),
          if (_activeJobId != null) ...[
            const SizedBox(height: 16),
            _buildActiveJob(),
          ],
          const SizedBox(height: 16),
          _buildHistorialGestor(),
        ],
      ),
    );
  }

  Widget _buildWorkersBanner() {
    return StreamBuilder<List<DoxeoWorker>>(
      stream: _queue.streamWorkers(),
      builder: (context, snap) {
        final workers = (snap.data ?? const <DoxeoWorker>[])
            .where((w) => w.online)
            .toList();
        final conTelegram = workers.where((w) => w.telegramOk).length;
        if (workers.isNotEmpty && conTelegram > 0) {
          return _banner(
            icon: Icons.check_circle_outline,
            color: AppTheme.success,
            text: '$conTelegram PC(s) con Telegram listo para consultar.',
          );
        }
        if (workers.isNotEmpty) {
          return _banner(
            icon: Icons.warning_amber_rounded,
            color: AppTheme.warning,
            text:
                'Hay ${workers.length} PC(s) conectadas pero sin sesión de Telegram. '
                'Inicia sesión con QR en el panel.',
          );
        }
        return _banner(
          icon: Icons.cloud_off,
          color: AppTheme.danger,
          text:
              'Ninguna PC con el sistema está conectada. La consulta quedará '
              'en cola hasta que una se conecte.',
        );
      },
    );
  }

  Widget _banner({
    required IconData icon,
    required Color color,
    required String text,
    Widget? action,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: TextStyle(fontSize: 12, color: color)),
          ),
          if (action != null) action,
        ],
      ),
    );
  }

  Widget _buildClientCard() {
    final selected = _selectedClient;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionTitle(number: '1', title: 'Elige el cliente'),
            const SizedBox(height: 10),
            if (selected != null)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: CircleAvatar(
                  backgroundColor: AppTheme.primaryLight,
                  child: Text(
                    selected.initials,
                    style: const TextStyle(color: AppTheme.primary),
                  ),
                ),
                title: Text(
                  selected.displayName,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                subtitle: Text(
                  'DNI ${selected.numeroDocumento.isEmpty ? "—" : selected.numeroDocumento}'
                  '${selected.codigoCliente.isEmpty ? "" : " · ${selected.codigoCliente}"}',
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.close),
                  tooltip: 'Cambiar cliente',
                  onPressed: () => setState(() => _selectedClient = null),
                ),
              )
            else ...[
              TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: 'Buscar por nombre, DNI o código… (opcional)',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  suffixIcon: _loadingClients
                      ? const Padding(
                          padding: EdgeInsets.all(10),
                          child: SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : null,
                ),
              ),
              ..._clientMatches.map(
                (c) => ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(c.displayName),
                  subtitle: Text(
                    'DNI ${c.numeroDocumento.isEmpty ? "—" : c.numeroDocumento}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _selectClient(c),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildQueryCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionTitle(number: '2', title: 'Elige la consulta'),
            const SizedBox(height: 10),
            StreamBuilder<List<DoxeoComando>>(
              stream: _queue.streamComandos(),
              builder: (context, snap) {
                final comandos = snap.data ?? const <DoxeoComando>[];
                final effectiveId =
                    comandos.any((c) => c.id == _selectedCommandId)
                        ? _selectedCommandId
                        : '';
                DoxeoComando? comandoSel;
                for (final c in comandos) {
                  if (c.id == effectiveId) {
                    comandoSel = c;
                    break;
                  }
                }
                final preview =
                    _dni.isEmpty ? '' : (comandoSel?.previewMessage(_dni) ?? _dni);
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    DropdownButtonFormField<String>(
                      value: effectiveId,
                      decoration: InputDecoration(
                        labelText: 'Consulta (comando)',
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                      items: [
                        const DropdownMenuItem(
                          value: '',
                          child: Text('Solo DNI (sin comando)'),
                        ),
                        ...comandos.map(
                          (c) => DropdownMenuItem(
                            value: c.id,
                            child: Text(
                              c.plantilla.isEmpty
                                  ? c.nombre
                                  : '${c.nombre} · ${c.plantilla}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                      onChanged: (value) =>
                          setState(() => _selectedCommandId = value ?? ''),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _dniController,
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        labelText: 'DNI a consultar',
                        border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                    if (preview.isNotEmpty) ...[
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
                    ],
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQueryButton() {
    String hint = '';
    if (_activeJobId != null) {
      hint = 'Espera a que termine la consulta en curso';
    } else if (_dni.length < 7) {
      hint = 'Elige un cliente o escribe un DNI válido';
    }
    return StreamBuilder<List<DoxeoComando>>(
      stream: _queue.streamComandos(),
      builder: (context, snap) {
        final comandos = snap.data ?? const <DoxeoComando>[];
        return Column(
          children: [
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _canQuery ? () => _runQuery(comandos) : null,
                icon: _launching
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.send),
                label: Text(_launching ? 'Encolando…' : 'Consultar'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            if (hint.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  hint,
                  style: const TextStyle(
                      fontSize: 11, color: AppTheme.textSecondary),
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
          return const Center(child: CircularProgressIndicator());
        }
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: DoxeoJobView(
              job: job,
              queue: _queue,
              onCancel: job.isPending
                  ? () => _queue.cancelarJob(job.id)
                  : null,
              onClose: job.isDone
                  ? () => setState(() => _activeJobId = null)
                  : null,
            ),
          ),
        );
      },
    );
  }

  Widget _buildHistorialGestor() {
    final profile = context.read<AuthService>().profile;
    if (profile == null) return const SizedBox.shrink();
    return StreamBuilder<List<DoxeoJob>>(
      stream: _queue.streamHistorialGestor(profile.uid),
      builder: (context, snap) {
        final jobs = (snap.data ?? const <DoxeoJob>[])
            .where((j) => j.id != _activeJobId)
            .toList();
        if (jobs.isEmpty) return const SizedBox.shrink();
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Mis consultas recientes',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                ),
                const SizedBox(height: 6),
                ...jobs.map(
                  (job) => ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    childrenPadding: EdgeInsets.zero,
                    dense: true,
                    leading: DoxeoJobStatusDot(estado: job.estado),
                    title: Text(
                      job.comandoNombre.isEmpty ? 'Solo DNI' : job.comandoNombre,
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(
                      'DNI ${job.dni}'
                      '${job.creadoAt == null ? "" : " · ${_fechaCorta(job.creadoAt!)}"}',
                      style: const TextStyle(
                          fontSize: 11, color: AppTheme.textSecondary),
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: DoxeoJobView(job: job, queue: _queue, compact: true),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  String _fechaCorta(DateTime fecha) {
    return '${fecha.day.toString().padLeft(2, '0')}/${fecha.month.toString().padLeft(2, '0')} '
        '${fecha.hour.toString().padLeft(2, '0')}:${fecha.minute.toString().padLeft(2, '0')}';
  }
}

class _SectionTitle extends StatelessWidget {
  final String number;
  final String title;

  const _SectionTitle({required this.number, required this.title});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 22,
          height: 22,
          alignment: Alignment.center,
          decoration: const BoxDecoration(
            color: AppTheme.primary,
            shape: BoxShape.circle,
          ),
          child: Text(
            number,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
        ),
      ],
    );
  }
}
