import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../services/campaign_service.dart';
import '../services/campaign_stats_service.dart';
import '../services/doxeo_api_service.dart';
import '../utils/contact_metrics_utils.dart';

/// Pantalla "Consultas Telegram": elige cliente → elige consulta (comando)
/// → el backend twi envía el mensaje al bot/contacto y devuelve la respuesta
/// con texto e imágenes.
class ConsultaTelegramScreen extends StatefulWidget {
  final ClientModel? initialClient;
  final String? campaignId;

  const ConsultaTelegramScreen({super.key, this.initialClient, this.campaignId});

  @override
  State<ConsultaTelegramScreen> createState() => _ConsultaTelegramScreenState();
}

class _ConsultaTelegramScreenState extends State<ConsultaTelegramScreen> {
  final _api = DoxeoApiService();
  final _campaignService = CampaignService();
  final _statsService = CampaignStatsService();
  final _searchController = TextEditingController();
  final _dniController = TextEditingController();

  bool _configLoaded = false;
  DoxeoStatus? _status;
  String? _statusError;

  List<DoxeoCommand> _commands = [];
  String _selectedCommandId = '';

  String? _campaignId;
  List<ClientModel> _allClients = [];
  bool _loadingClients = false;
  bool _clientsLoadedOnce = false;
  ClientModel? _selectedClient;
  Timer? _debounce;

  bool _running = false;
  DoxeoQueryResult? _result;

  @override
  void initState() {
    super.initState();
    _selectedClient = widget.initialClient;
    _campaignId = widget.campaignId;
    if (_selectedClient != null) {
      _dniController.text = _selectedClient!.numeroDocumento;
    }
    _searchController.addListener(_onSearchChanged);
    _dniController.addListener(() => setState(() {}));
    _bootstrap();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _dniController.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    await _api.load();
    if (!mounted) return;
    setState(() => _configLoaded = true);
    if (_api.isConfigured) {
      await _refreshRemote();
    }
    _campaignId ??= await _campaignService.getActiveCampaignId();
    // Si venimos con un cliente, precargar lista para permitir cambiar.
    if (_selectedClient != null) {
      unawaited(_ensureClientsLoaded());
    }
  }

  Future<void> _refreshRemote() async {
    setState(() => _statusError = null);
    try {
      final status = await _api.getStatus();
      final commands = await _api.listCommands();
      if (!mounted) return;
      setState(() {
        _status = status;
        _commands = commands;
        if (_selectedCommandId.isNotEmpty &&
            !_commands.any((c) => c.id == _selectedCommandId)) {
          _selectedCommandId = '';
        }
      });
    } on DoxeoException catch (e) {
      if (!mounted) return;
      setState(() => _statusError = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _statusError = 'Sin conexión con el servidor: $e');
    }
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

  DoxeoCommand? get _selectedCommand {
    if (_selectedCommandId.isEmpty) return null;
    for (final c in _commands) {
      if (c.id == _selectedCommandId) return c;
    }
    return null;
  }

  String get _dni => _dniController.text.replaceAll(RegExp(r'[^0-9A-Za-z]'), '');

  String get _messagePreview {
    final dni = _dni;
    if (dni.isEmpty) return '';
    final cmd = _selectedCommand;
    if (cmd == null) return dni;
    return cmd.previewMessage(dni);
  }

  bool get _canQuery =>
      _api.isConfigured &&
      !_running &&
      _dni.length >= 7 &&
      (_status?.sessionAuthorized ?? false);

  Future<void> _runQuery() async {
    final dni = _dni;
    if (dni.length < 7) return;
    setState(() {
      _running = true;
      _result = null;
    });
    try {
      final result = await _api.runQuery(
        dni: dni,
        commandId: _selectedCommandId.isEmpty ? null : _selectedCommandId,
        timeoutSec: 60,
      );
      if (!mounted) return;
      setState(() => _result = result);
    } on DoxeoException catch (e) {
      _showSnack(e.message, isError: true);
    } on TimeoutException {
      _showSnack('La consulta tardó demasiado. Intenta de nuevo.', isError: true);
    } catch (e) {
      _showSnack('Error de conexión: $e', isError: true);
    } finally {
      if (mounted) setState(() => _running = false);
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

  Future<void> _openSettings() async {
    final baseCtrl = TextEditingController(
      text: _api.baseUrl.isEmpty ? 'http://192.168.1.100:8080' : _api.baseUrl,
    );
    final keyCtrl = TextEditingController(text: _api.apiKey);
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Conexión con el servidor'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'URL del panel de cobranzas (PC encendida con el sistema) y la '
              'API Key móvil definida en Configuraciones → Telegram.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: baseCtrl,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(
                labelText: 'URL base (ej. http://192.168.1.100:8080)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: keyCtrl,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'API Key móvil',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    if (saved == true) {
      await _api.save(baseUrl: baseCtrl.text, apiKey: keyCtrl.text);
      if (!mounted) return;
      setState(() {});
      _showSnack('Conexión guardada');
      await _refreshRemote();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Consulta Telegram'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Conexión con el servidor',
            onPressed: _openSettings,
          ),
        ],
      ),
      body: !_configLoaded
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshRemote,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (!_api.isConfigured)
                    _buildConfigNeededCard()
                  else ...[
                    _buildStatusBanner(),
                    const SizedBox(height: 12),
                    _buildClientCard(),
                    const SizedBox(height: 12),
                    _buildQueryCard(),
                    const SizedBox(height: 16),
                    _buildQueryButton(),
                    if (_result != null) ...[
                      const SizedBox(height: 16),
                      _buildResultCard(_result!),
                    ],
                  ],
                ],
              ),
            ),
    );
  }

  Widget _buildConfigNeededCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Icon(Icons.link_off, size: 40, color: AppTheme.textMuted),
            const SizedBox(height: 12),
            const Text(
              'Falta conectar con el servidor de cobranzas',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 6),
            const Text(
              'Configura la URL del panel y la API Key móvil para hacer consultas por Telegram.',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: _openSettings,
              icon: const Icon(Icons.settings),
              label: const Text('Configurar conexión'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBanner() {
    if (_statusError != null) {
      return _banner(
        icon: Icons.cloud_off,
        color: AppTheme.danger,
        text: _statusError!,
        action: TextButton(onPressed: _refreshRemote, child: const Text('Reintentar')),
      );
    }
    final status = _status;
    if (status == null) {
      return _banner(
        icon: Icons.sync,
        color: AppTheme.warning,
        text: 'Comprobando conexión…',
      );
    }
    if (!status.sessionAuthorized) {
      return _banner(
        icon: Icons.warning_amber_rounded,
        color: AppTheme.danger,
        text:
            'El servidor no tiene sesión de Telegram activa. Inicia sesión con QR en el panel web.',
      );
    }
    return _banner(
      icon: Icons.check_circle_outline,
      color: AppTheme.success,
      text:
          'Telegram conectado (${status.userName}) · ${status.commands} consulta(s) disponibles',
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
                  hintText: 'Buscar por nombre, DNI o código…',
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
            DropdownButtonFormField<String>(
              value: _selectedCommandId,
              decoration: InputDecoration(
                labelText: 'Consulta (comando)',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              items: [
                const DropdownMenuItem(
                  value: '',
                  child: Text('Solo DNI (sin comando)'),
                ),
                ..._commands.map(
                  (c) => DropdownMenuItem(
                    value: c.id,
                    child: Text(
                      c.command.isEmpty ? c.name : '${c.name} · ${c.command}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ],
              onChanged: (value) =>
                  setState(() => _selectedCommandId = value ?? ''),
            ),
            if (_selectedCommand?.description.isNotEmpty == true) ...[
              const SizedBox(height: 6),
              Text(
                _selectedCommand!.description,
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ],
            const SizedBox(height: 10),
            TextField(
              controller: _dniController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: 'DNI a consultar',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            if (_messagePreview.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.primaryLight,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  'Se enviará: $_messagePreview',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primaryDark,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildQueryButton() {
    String hint = '';
    if (_api.isConfigured) {
      if (!(_status?.sessionAuthorized ?? false)) {
        hint = 'Sin sesión de Telegram en el servidor';
      } else if (_dni.length < 7) {
        hint = 'Elige un cliente o escribe un DNI válido';
      }
    }
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: _canQuery ? _runQuery : null,
            icon: _running
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.send),
            label: Text(_running ? 'Consultando…' : 'Consultar'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
        ),
        if (_running)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
              'Esperando respuesta de Telegram (puede tardar hasta 1 min)…',
              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
          )
        else if (hint.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              hint,
              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
          ),
      ],
    );
  }

  Widget _buildResultCard(DoxeoQueryResult result) {
    final images = result.repliesWithImage;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _statusChip(result),
                const SizedBox(width: 8),
                if (result.commandName.isNotEmpty)
                  Chip(
                    label: Text(result.commandName),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
            if (result.error.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(result.error, style: const TextStyle(color: AppTheme.danger)),
            ],
            if (result.messageSent.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Enviado: ${result.messageSent}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
            ],
            if (result.nombre.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('Nombre', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
              Text(
                result.nombre,
                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
              ),
            ],
            if (result.phones.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('Teléfonos', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: result.phones
                    .map(
                      (p) => Chip(
                        avatar: const Icon(Icons.phone, size: 14),
                        label: Text(p),
                        visualDensity: VisualDensity.compact,
                      ),
                    )
                    .toList(),
              ),
            ],
            if (result.addresses.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('Direcciones', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
              ...result.addresses.map(
                (a) => Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text('• $a', style: const TextStyle(fontSize: 13)),
                ),
              ),
            ],
            if (result.rawReply.isNotEmpty) ...[
              const SizedBox(height: 10),
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Respuesta completa', style: TextStyle(fontSize: 13)),
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.divider,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: SelectableText(
                      result.rawReply,
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ],
              ),
            ],
            if (images.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('Imágenes', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: images.map((r) => _imageThumb(r)).toList(),
              ),
            ],
            if (result.replies.isEmpty && result.error.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                  'Sin respuesta del bot/contacto en el tiempo de espera.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _statusChip(DoxeoQueryResult result) {
    final ok = result.isOk;
    final timeout = result.status == 'timeout';
    final color = ok
        ? AppTheme.success
        : timeout
            ? AppTheme.warning
            : AppTheme.danger;
    final label = ok
        ? 'OK'
        : timeout
            ? 'Sin respuesta'
            : 'Error';
    return Chip(
      avatar: Icon(
        ok ? Icons.check_circle : Icons.error_outline,
        size: 16,
        color: color,
      ),
      label: Text(label, style: TextStyle(color: color)),
      visualDensity: VisualDensity.compact,
      side: BorderSide(color: color.withValues(alpha: 0.4)),
    );
  }

  Widget _imageThumb(DoxeoReply reply) {
    final bytes = base64Decode(reply.media!.dataBase64);
    return GestureDetector(
      onTap: () => _showFullImage(bytes),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Image.memory(
          bytes,
          width: 110,
          height: 110,
          fit: BoxFit.cover,
        ),
      ),
    );
  }

  void _showFullImage(dynamic bytes) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        insetPadding: const EdgeInsets.all(12),
        child: InteractiveViewer(
          child: Image.memory(bytes, fit: BoxFit.contain),
        ),
      ),
    );
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
