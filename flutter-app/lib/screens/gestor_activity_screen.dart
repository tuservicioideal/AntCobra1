import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../config/theme.dart';
import '../models/gestor_activity.dart';
import '../models/user_model.dart';
import '../services/firestore_service.dart';
import '../utils/section_utils.dart';

class GestorActivityScreen extends StatefulWidget {
  const GestorActivityScreen({super.key});

  @override
  State<GestorActivityScreen> createState() => _GestorActivityScreenState();
}

class _GestorActivityScreenState extends State<GestorActivityScreen> {
  final _firestore = FirestoreService();
  final _prettyDateFmt = DateFormat('dd/MM/yyyy');
  final _timeFmt = DateFormat('HH:mm');

  bool _loading = true;
  String? _error;
  DateTime _selectedDay = DateTime.now();
  String _canalFilter = 'todos';
  String? _sectionFilter;
  List<UserModel> _gestores = [];
  List<GestorActivityEntry> _entries = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final gestores = await _firestore.getGestoresActivos();
      final feed = await _firestore.getGestorActivityFeed(
        day: _selectedDay,
        gestorUids: gestores.map((g) => g.uid).where((uid) => uid.isNotEmpty).toList(),
      );
      if (!mounted) return;
      setState(() {
        _gestores = gestores;
        _entries = feed;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDay,
      firstDate: DateTime.now().subtract(const Duration(days: 90)),
      lastDate: DateTime.now(),
      locale: const Locale('es', 'PE'),
    );
    if (picked == null || !mounted) return;
    setState(() => _selectedDay = picked);
    await _loadData();
  }

  List<_GestorBucket> get _visibleBuckets {
    final filteredGestores = _gestores.where((gestor) {
      if (_canalFilter == 'call' && !gestor.isCallGestor) return false;
      if (_canalFilter == 'campo' && !gestor.isFieldGestor) return false;
      if (_sectionFilter == null || _sectionFilter!.isEmpty) return true;
      return _primarySectionKey(gestor) == _sectionFilter;
    }).toList()
      ..sort((a, b) => a.nombre.toLowerCase().compareTo(b.nombre.toLowerCase()));

    return filteredGestores.map((gestor) {
      final entries = _entries.where((item) => item.gestorUid == gestor.uid).toList()
        ..sort((a, b) => b.sortKey.compareTo(a.sortKey));
      return _GestorBucket(
        gestor: gestor,
        entries: entries,
      );
    }).toList();
  }

  String _primarySectionKey(UserModel gestor) {
    final keys = resolveGestorSectionKeys(gestor);
    if (keys.isNotEmpty) return keys.first;
    return gestor.seccion;
  }

  List<DropdownMenuItem<String?>> get _sectionOptions {
    final seen = <String>{};
    final items = <DropdownMenuItem<String?>>[
      const DropdownMenuItem<String?>(value: null, child: Text('Todas')),
    ];
    for (final gestor in _gestores) {
      final key = _primarySectionKey(gestor).trim();
      if (key.isEmpty || !seen.add(key)) continue;
      items.add(
        DropdownMenuItem<String?>(
          value: key,
          child: Text(sectionDisplayLabel(key)),
        ),
      );
    }
    return items;
  }

  @override
  Widget build(BuildContext context) {
    final buckets = _visibleBuckets;
    final allEntries = buckets.expand((b) => b.entries).toList();
    final totalGestiones = allEntries.where((e) => e.isGestion).length;
    final totalLlamadas = allEntries.where((e) => e.isCallAttempt).length;
    final totalWhatsApps = allEntries.where((e) => e.isWhatsAppAttempt).length;
    final gestoresConActividad = buckets.where((b) => b.entries.isNotEmpty).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Actividad de gestores'),
        actions: [
          IconButton(
            tooltip: 'Fecha',
            onPressed: _pickDate,
            icon: const Icon(Icons.calendar_today_outlined, color: Colors.white),
          ),
          IconButton(
            tooltip: 'Actualizar',
            onPressed: _loading ? null : _loadData,
            icon: const Icon(Icons.refresh, color: Colors.white),
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppTheme.primaryColor),
            )
          : _error != null
              ? _buildError()
              : RefreshIndicator(
                  color: AppTheme.primaryColor,
                  onRefresh: _loadData,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                    children: [
                      _buildHeader(),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _kpiCard('Gestores con actividad', '$gestoresConActividad', Icons.groups),
                          _kpiCard('Gestiones', '$totalGestiones', Icons.assignment_turned_in_outlined),
                          _kpiCard('Llamadas', '$totalLlamadas', Icons.call_outlined),
                          _kpiCard('WhatsApp', '$totalWhatsApps', Icons.chat_outlined),
                        ],
                      ),
                      const SizedBox(height: 12),
                      _buildFilters(),
                      const SizedBox(height: 12),
                      if (buckets.isEmpty)
                        _buildEmpty()
                      else
                        ...buckets.map(_buildGestorCard),
                    ],
                  ),
                ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Actividad del ${_prettyDateFmt.format(_selectedDay)}',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Text(
          'Supervisa gestiones, llamadas y aperturas de WhatsApp por gestor.',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
      ],
    );
  }

  Widget _buildFilters() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: _canalFilter,
                    decoration: const InputDecoration(
                      labelText: 'Canal',
                      isDense: true,
                    ),
                    items: const [
                      DropdownMenuItem(value: 'todos', child: Text('Todos')),
                      DropdownMenuItem(value: 'campo', child: Text('Campo')),
                      DropdownMenuItem(value: 'call', child: Text('Call center')),
                    ],
                    onChanged: (value) {
                      if (value == null) return;
                      setState(() => _canalFilter = value);
                    },
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: DropdownButtonFormField<String?>(
                    value: _sectionFilter,
                    decoration: const InputDecoration(
                      labelText: 'Sección',
                      isDense: true,
                    ),
                    items: _sectionOptions,
                    onChanged: (value) {
                      setState(() => _sectionFilter = value);
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGestorCard(_GestorBucket bucket) {
    final gestor = bucket.gestor;
    final entries = bucket.entries;
    final gestiones = entries.where((e) => e.isGestion).length;
    final llamadas = entries.where((e) => e.isCallAttempt).length;
    final whatsapps = entries.where((e) => e.isWhatsAppAttempt).length;
    final last = entries.isEmpty ? null : entries.first.timestamp;
    final sectionKey = _primarySectionKey(gestor);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        leading: CircleAvatar(
          backgroundColor: gestor.isCallGestor
              ? AppTheme.info.withValues(alpha: 0.18)
              : AppTheme.primaryColor.withValues(alpha: 0.16),
          child: Icon(
            gestor.isCallGestor ? Icons.headset_mic_outlined : Icons.directions_walk,
            color: gestor.isCallGestor ? AppTheme.info : AppTheme.primaryColor,
          ),
        ),
        title: Text(
          gestor.nombre.isNotEmpty ? gestor.nombre : gestor.email,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          [
            gestor.isCallGestor ? 'Call center' : 'Campo',
            if (sectionKey.isNotEmpty) sectionDisplayLabel(sectionKey),
            if (last != null) 'Última ${_timeFmt.format(last)}',
            if (last == null) 'Sin actividad hoy',
          ].join(' · '),
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
        trailing: Wrap(
          spacing: 6,
          children: [
            _miniCountChip(Icons.assignment_turned_in_outlined, '$gestiones'),
            _miniCountChip(Icons.call_outlined, '$llamadas'),
            _miniCountChip(Icons.chat_outlined, '$whatsapps'),
          ],
        ),
        children: [
          if (entries.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'No hay actividad registrada para este gestor en la fecha seleccionada.',
                style: TextStyle(color: Colors.grey.shade600),
              ),
            )
          else
            ...entries.map(_buildEntryTile),
        ],
      ),
    );
  }

  Widget _buildEntryTile(GestorActivityEntry entry) {
    final icon = switch (entry.type) {
      'llamada_iniciada' => Icons.call_outlined,
      'whatsapp_abierto' => Icons.chat_outlined,
      _ => Icons.assignment_turned_in_outlined,
    };
    final color = switch (entry.type) {
      'llamada_iniciada' => AppTheme.primaryColor,
      'whatsapp_abierto' => AppTheme.success,
      _ => AppTheme.info,
    };

    return Container(
      margin: const EdgeInsets.only(top: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.18)),
        color: color.withValues(alpha: 0.05),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.12),
          child: Icon(icon, color: color, size: 18),
        ),
        title: Text(
          entry.clientName.isNotEmpty ? entry.clientName : entry.displayType,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        subtitle: Text(
          [
            if (entry.timestamp != null) _timeFmt.format(entry.timestamp!),
            entry.displayType,
            if (entry.estadoGestion.isNotEmpty) entry.estadoGestion,
            if (entry.phone.isNotEmpty) entry.phone,
            if (entry.isContactAction && !entry.launchSuccess) 'no se abrió',
          ].join(' · '),
          style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
        ),
        trailing: entry.isGestion
            ? const Icon(Icons.history, size: 18)
            : Icon(
                entry.launchSuccess ? Icons.check_circle_outline : Icons.error_outline,
                size: 18,
                color: entry.launchSuccess ? AppTheme.success : AppTheme.warning,
              ),
      ),
    );
  }

  Widget _buildEmpty() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(Icons.event_busy_outlined, size: 42, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(
              'No hay gestores para los filtros seleccionados.',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.cloud_off_outlined, size: 44, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            const Text(
              'No se pudo cargar la actividad',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(
              _error ?? 'Error desconocido',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh),
              label: const Text('Reintentar'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _kpiCard(String label, String value, IconData icon) {
    return Container(
      constraints: const BoxConstraints(minWidth: 150),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.12),
            child: Icon(icon, color: AppTheme.primaryColor, size: 18),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
              ),
              Text(
                value,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _miniCountChip(IconData icon, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppTheme.primaryColor),
          const SizedBox(width: 4),
          Text(
            value,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _GestorBucket {
  final UserModel gestor;
  final List<GestorActivityEntry> entries;

  const _GestorBucket({
    required this.gestor,
    required this.entries,
  });
}
