import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../models/user_model.dart';
import '../services/auth_service.dart';
import '../services/campaign_service.dart';
import '../services/firestore_service.dart';
import '../utils/section_utils.dart';
import '../widgets/destination_gestor_picker.dart';
import '../widgets/paginated_client_checkbox_list.dart';

const _motivoLabels = {
  'zona_inaccesible': 'Zona inaccesible',
  'ruta_bloqueada': 'Ruta bloqueada',
  'riesgo_seguridad': 'Riesgo de seguridad',
  'otro': 'Otro',
};

/// Pantalla admin para devoluciones, pool y transferencia de cartera.
class ReassignmentScreen extends StatefulWidget {
  const ReassignmentScreen({super.key});

  @override
  State<ReassignmentScreen> createState() => _ReassignmentScreenState();
}

class _ReassignmentScreenState extends State<ReassignmentScreen>
    with SingleTickerProviderStateMixin {
  final _firestore = FirestoreService();
  final _campaignService = CampaignService();

  late TabController _tabs;
  bool _loading = true;
  bool _busy = false;
  String? _campaignId;

  List<Map<String, dynamic>> _pending = [];
  List<Map<String, dynamic>> _pool = [];
  List<Map<String, dynamic>> _especial = [];
  List<UserModel> _gestores = [];
  List<DestinationOption> _destOptions = [];
  String? _selectedDest;

  // Transfer tab state
  UserModel? _sourceGestor;
  List<ClientModel> _sourceClients = [];
  final Set<String> _selectedClientIds = {};
  String? _transferDest;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final campaignId = await _campaignService.getActiveCampaignId();
    if (!mounted) return;
    if (campaignId == null) {
      setState(() {
        _loading = false;
        _campaignId = null;
      });
      return;
    }

    final results = await Future.wait([
      _firestore.listPendingReturns(campaignId),
      _firestore.listPoolClients(campaignId),
      _firestore.listGestionEspecialClients(campaignId),
      _firestore.getGestoresActivos(),
      _firestore.resolveDestinationSections(campaignId),
    ]);

    final gestores = results[3] as List<UserModel>;
    final sections = (results[4] as List<String>);
    final destOptions = buildDestinationOptions(
      gestores: gestores,
      destinationSections: sections,
    );

    if (!mounted) return;
    setState(() {
      _campaignId = campaignId;
      _pending = results[0] as List<Map<String, dynamic>>;
      _pool = results[1] as List<Map<String, dynamic>>;
      _especial = results[2] as List<Map<String, dynamic>>;
      _gestores = gestores;
      _destOptions = destOptions;
      _selectedDest = destOptions.isNotEmpty ? destOptions.first.sectionKey : null;
      _transferDest = _selectedDest;
      _loading = false;
    });
  }

  String get _adminEmail =>
      context.read<AuthService>().profile?.email ?? '';
  String get _adminName =>
      context.read<AuthService>().profile?.nombre ?? '';

  Future<void> _runAction(Future<Map<String, dynamic>> Function() action) async {
    if (_busy || _campaignId == null) return;
    setState(() => _busy = true);
    final result = await action();
    if (!mounted) return;
    setState(() => _busy = false);
    if (result['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Operación completada')),
      );
      await _load();
    } else {
      final err = result['error'] ??
          (result['errors'] is List && (result['errors'] as List).isNotEmpty
              ? (result['errors'] as List).first
              : 'Error en la operación');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$err'), backgroundColor: AppTheme.danger),
      );
    }
  }

  Future<void> _reassignItem(Map<String, dynamic> item) async {
    final dest = _selectedDest;
    if (dest == null || dest.isEmpty) return;
    final clientId = item['client_id']?.toString() ?? '';
    final section = item['seccion_key']?.toString() ?? '';
    await _runAction(() => _firestore.reassignReturnedClient(
          campaignId: _campaignId!,
          currentSectionKey: section,
          clientId: clientId,
          newSectionKey: dest,
          adminEmail: _adminEmail,
          adminName: _adminName,
          gestoresCache: _gestores,
        ));
  }

  Future<void> _moveToPool(Map<String, dynamic> item) async {
    await _runAction(() => _firestore.moveClientToPool(
          campaignId: _campaignId!,
          currentSectionKey: item['seccion_key']?.toString() ?? '',
          clientId: item['client_id']?.toString() ?? '',
          adminEmail: _adminEmail,
          adminName: _adminName,
        ));
  }

  Future<void> _toGestionEspecial(Map<String, dynamic> item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Gestión especial'),
        content: Text(
          '¿Derivar ${item['codigo_cliente']} a gestión especial?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Confirmar')),
        ],
      ),
    );
    if (confirmed != true) return;
    await _runAction(() => _firestore.moveClientToGestionEspecial(
          campaignId: _campaignId!,
          currentSectionKey: item['seccion_key']?.toString() ?? '',
          clientId: item['client_id']?.toString() ?? '',
          adminEmail: _adminEmail,
          adminName: _adminName,
          motivo: item['motivo_devolucion']?.toString() ?? 'zona_inaccesible',
        ));
  }

  Future<void> _rejectReturn(Map<String, dynamic> item) async {
    final noteCtrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Rechazar devolución'),
        content: TextField(
          controller: noteCtrl,
          decoration: const InputDecoration(
            labelText: 'Nota (opcional)',
            border: OutlineInputBorder(),
          ),
          maxLines: 2,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Rechazar', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    final note = noteCtrl.text.trim();
    noteCtrl.dispose();
    if (confirmed != true) return;
    await _runAction(() => _firestore.rejectReturnRequest(
          campaignId: _campaignId!,
          seccionKey: item['seccion_key']?.toString() ?? '',
          clientId: item['client_id']?.toString() ?? '',
          adminEmail: _adminEmail,
          adminName: _adminName,
          rejectionNote: note,
          gestoresCache: _gestores,
        ));
  }

  Future<void> _restoreEspecial(Map<String, dynamic> item) async {
    final origen = item['seccion_origen']?.toString() ?? '';
    if (origen.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Sin sección de origen registrada')),
      );
      return;
    }
    await _runAction(() => _firestore.restoreFromGestionEspecial(
          campaignId: _campaignId!,
          clientId: item['client_id']?.toString() ?? '',
          seccionOrigen: origen,
          adminEmail: _adminEmail,
          adminName: _adminName,
        ));
  }

  List<DestinationOption> get _transferDestOptions {
    if (_sourceGestor == null) return _destOptions;
    final sourceKeys = resolveGestorSectionKeys(_sourceGestor!).toSet();
    if (_sourceGestor!.isCallGestor) {
      sourceKeys.add(callSectionKeyForUid(_sourceGestor!.uid));
    }
    return _destOptions
        .where((o) => !sourceKeys.contains(o.sectionKey))
        .toList();
  }

  Future<void> _loadSourceClients(UserModel? gestor) async {
    _sourceGestor = gestor;
    _sourceClients = [];
    _selectedClientIds.clear();
    if (gestor == null || _campaignId == null) {
      setState(() {});
      return;
    }
    setState(() => _busy = true);
    var sections = resolveGestorSectionKeys(gestor);
    if (gestor.isCallGestor && sections.isEmpty) {
      sections = [callSectionKeyForUid(gestor.uid)];
    }
    final all = <ClientModel>[];
    for (final sec in sections) {
      final clients = await _firestore.getClients(_campaignId!, sec);
      all.addAll(clients);
    }
    if (!mounted) return;
    final destOpts = _transferDestOptions;
    setState(() {
      _sourceClients = all;
      _transferDest = destOpts.isNotEmpty
          ? destOpts.first.sectionKey
          : null;
      _busy = false;
    });
  }

  Future<void> _bulkTransfer() async {
    if (_transferDest == null || _selectedClientIds.isEmpty) return;
    final clients = _sourceClients
        .where((c) => _selectedClientIds.contains(c.id))
        .map((c) => {
              'client_id': c.id,
              'seccion_key': c.seccionKey.isNotEmpty ? c.seccionKey : c.seccion,
            })
        .where((m) =>
            (m['seccion_key'] ?? '').isNotEmpty &&
            m['seccion_key'] != _transferDest)
        .toList();

    if (clients.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Los clientes seleccionados ya están en la sección destino.',
          ),
        ),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar transferencia'),
        content: Text(
          '¿Mover ${clients.length} cliente(s) a '
          '${sectionDisplayLabel(_transferDest!)}?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Transferir')),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _busy = true);
    final result = await _firestore.reassignClientsBulk(
      campaignId: _campaignId!,
      clients: clients,
      newSectionKey: _transferDest!,
      adminEmail: _adminEmail,
      adminName: _adminName,
      motivo: 'reasignacion_manual',
      resetGestion: false,
      gestoresCache: _gestores,
    );
    if (!mounted) return;
    setState(() => _busy = false);
    final ok = result['ok'] ?? 0;
    final failed = result['failed'] ?? 0;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Transferidos: $ok · Fallidos: $failed'),
        backgroundColor: failed > 0 ? AppTheme.warning : AppTheme.success,
      ),
    );
    _selectedClientIds.clear();
    await _load();
    if (_sourceGestor != null) await _loadSourceClients(_sourceGestor);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    if (!auth.canManageUsers) {
      return Scaffold(
        appBar: AppBar(title: const Text('Reasignación')),
        body: const Center(child: Text('Acceso restringido a administradores')),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Reasignar / Devoluciones'),
        bottom: TabBar(
          controller: _tabs,
          tabs: [
            Tab(text: 'Devoluciones (${_pending.length})'),
            Tab(text: 'Pool (${_pool.length + _especial.length})'),
            const Tab(text: 'Transferir'),
          ],
        ),
        actions: [
          if (_busy)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              ),
            )
          else
            IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _campaignId == null
              ? const Center(child: Text('No hay campaña activa'))
              : TabBarView(
                  controller: _tabs,
                  children: [
                    _buildReturnsTab(),
                    _buildPoolTab(),
                    _buildTransferTab(),
                  ],
                ),
    );
  }

  Widget _buildKpiBar() {
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            _kpiChip('Pendientes', _pending.length, AppTheme.warning),
            const SizedBox(width: 16),
            _kpiChip('Pool', _pool.length, AppTheme.info),
            const SizedBox(width: 16),
            _kpiChip('Especial', _especial.length, AppTheme.accent),
          ],
        ),
      ),
    );
  }

  Widget _kpiChip(String label, int count, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        Text('$count', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
      ],
    );
  }

  Widget _buildDestSelector() {
    if (_destOptions.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: DestinationGestorPicker(
            options: _destOptions,
            selectedSectionKey: _selectedDest,
            enabled: !_busy,
            onChanged: (v) => setState(() => _selectedDest = v),
          ),
        ),
      ),
    );
  }

  Widget _buildReturnsTab() {
    return Column(
      children: [
        _buildKpiBar(),
        _buildDestSelector(),
        Expanded(
          child: _pending.isEmpty
              ? _emptyState('No hay devoluciones pendientes.\n'
                  'Los gestores solicitan devolución desde la app.')
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: _pending.length,
                  itemBuilder: (_, i) => _returnCard(_pending[i], inPool: false),
                ),
        ),
      ],
    );
  }

  Widget _buildPoolTab() {
    return Column(
      children: [
        _buildKpiBar(),
        _buildDestSelector(),
        Expanded(
          child: (_pool.isEmpty && _especial.isEmpty)
              ? _emptyState('Pool y gestión especial vacíos.')
              : ListView(
                  padding: const EdgeInsets.all(12),
                  children: [
                    if (_pool.isNotEmpty) ...[
                      const Text('Pool de reasignación',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(height: 8),
                      ..._pool.map((i) => _returnCard(i, inPool: true)),
                    ],
                    if (_especial.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      const Text('Gestión especial',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(height: 8),
                      ..._especial.map(_especialCard),
                    ],
                  ],
                ),
        ),
      ],
    );
  }

  Widget _buildTransferTab() {
    final gestorOptions = _gestores;
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Gestor origen',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  value: _sourceGestor?.uid,
                  isExpanded: true,
                  decoration: InputDecoration(
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  hint: const Text('Seleccionar gestor'),
                  items: gestorOptions
                      .map((g) => DropdownMenuItem(
                            value: g.uid,
                            child: Text(
                              '${g.nombre} (${g.isCallGestor ? 'Call' : 'Campo'})',
                              style: const TextStyle(fontSize: 13),
                            ),
                          ))
                      .toList(),
                  onChanged: _busy
                      ? null
                      : (uid) {
                          if (uid == null) return;
                          final g = gestorOptions.firstWhere((x) => x.uid == uid);
                          _loadSourceClients(g);
                        },
                ),
              ],
            ),
          ),
        ),
        if (_sourceClients.isNotEmpty) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: DestinationGestorPicker(
                label: 'Gestor / sección destino',
                options: _transferDestOptions,
                selectedSectionKey: _transferDest,
                enabled: !_busy,
                onChanged: (v) => setState(() => _transferDest = v),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${_selectedClientIds.length} de ${_sourceClients.length} seleccionados',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
          const SizedBox(height: 8),
          PaginatedClientCheckboxList(
            clients: _sourceClients,
            selected: _selectedClientIds,
            enabled: !_busy,
            height: 320,
            onSelectionChanged: (s) => setState(() {
              _selectedClientIds
                ..clear()
                ..addAll(s);
            }),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _busy || _selectedClientIds.isEmpty ? null : _bulkTransfer,
              icon: const Icon(Icons.swap_horiz, color: Colors.white),
              label: Text(
                'Transferir ${_selectedClientIds.length} cliente(s)',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ] else if (_sourceGestor != null && !_busy) ...[
          const SizedBox(height: 24),
          Center(
            child: Text(
              'Este gestor no tiene clientes en sus secciones.',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ),
        ],
      ],
    );
  }

  Widget _emptyState(String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Text(
          message,
          textAlign: TextAlign.center,
          style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
        ),
      ),
    );
  }

  Widget _returnCard(Map<String, dynamic> item, {required bool inPool}) {
    final codigo = item['codigo_cliente']?.toString() ?? item['client_id']?.toString() ?? '';
    final nombre = item['nombre_completo']?.toString() ?? '—';
    final seccion = item['seccion_key']?.toString() ?? '';
    final motivoKey = item['motivo_devolucion']?.toString() ?? '';
    final motivo = _motivoLabels[motivoKey] ?? motivoKey;
    final gestor = item['devolucion_gestor_nombre']?.toString() ??
        item['gestor_devolucion_nombre']?.toString() ??
        '—';
    final nota = item['nota_devolucion']?.toString() ?? '';
    final fecha = item['devolucion_solicitada_at']?.toString() ?? '';

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$nombre · $codigo',
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 4),
            Text(
              'Sección: ${sectionDisplayLabel(seccion)} · Gestor: $gestor · $motivo',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
            if (nota.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Nota: $nota', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
              ),
            if (fecha.isNotEmpty)
              Text('Solicitado: ${fecha.length > 19 ? fecha.substring(0, 19) : fecha}',
                  style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                if (!inPool) ...[
                  _actionBtn('Pool', _busy ? null : () => _moveToPool(item), AppTheme.textSecondary),
                  _actionBtn('Especial', _busy ? null : () => _toGestionEspecial(item), AppTheme.warning),
                  _actionBtn('Rechazar', _busy ? null : () => _rejectReturn(item), AppTheme.danger),
                ],
                _actionBtn('Reasignar', _busy ? null : () => _reassignItem(item), AppTheme.success),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _especialCard(Map<String, dynamic> item) {
    final codigo = item['codigo_cliente']?.toString() ?? '';
    final nombre = item['nombre_completo']?.toString() ?? '—';
    final origen = item['seccion_origen']?.toString() ?? '—';
    final motivo = item['motivo_gestion_especial']?.toString() ?? '—';

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$nombre · $codigo',
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            Text('Origen: ${sectionDisplayLabel(origen)} · $motivo',
                style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              children: [
                _actionBtn('Restituir', _busy ? null : () => _restoreEspecial(item), AppTheme.success),
                _actionBtn('Reasignar', _busy ? null : () => _reassignItem(item), AppTheme.primaryColor),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionBtn(String label, VoidCallback? onTap, Color color) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        foregroundColor: color,
        side: BorderSide(color: color.withValues(alpha: 0.5)),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
      child: Text(label, style: const TextStyle(fontSize: 12)),
    );
  }
}
