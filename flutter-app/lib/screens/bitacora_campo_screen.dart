import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/theme.dart';
import '../models/bitacora_campo_entry.dart';
import '../services/bitacora_campo_service.dart';
import '../services/doxeo_queue_service.dart';
import '../services/firestore_service.dart';
import '../utils/section_utils.dart';
import 'client_detail_screen.dart';

/// Panel admin/supervisor: GPS, Telegram y notas en un feed consultable.
class BitacoraCampoScreen extends StatefulWidget {
  const BitacoraCampoScreen({super.key});

  @override
  State<BitacoraCampoScreen> createState() => _BitacoraCampoScreenState();
}

class _BitacoraCampoScreenState extends State<BitacoraCampoScreen> {
  final _bitacora = BitacoraCampoService();
  final _doxeo = DoxeoQueueService();
  final _firestore = FirestoreService();
  final _searchController = TextEditingController();
  final _prettyDateFmt = DateFormat('dd/MM/yyyy');
  final _timeFmt = DateFormat('HH:mm');

  bool _loading = true;
  String? _error;
  DateTime _selectedDay = DateTime.now();
  String _tipoFilter = 'todos';
  String? _sectionFilter;
  List<BitacoraCampoEntry> _entries = [];
  String _localQuery = '';

  @override
  void initState() {
    super.initState();
    _searchController.addListener(() {
      setState(() => _localQuery = _searchController.text);
    });
    _loadData();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final dniNeedle = _digitsOnly(_searchController.text);
      final feed = await _bitacora.queryFeed(
        day: _selectedDay,
        tipo: _tipoFilter,
        dni: dniNeedle.length >= 7 ? dniNeedle : null,
        seccionKey: _sectionFilter,
      );
      if (!mounted) return;
      setState(() {
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

  String _digitsOnly(String raw) =>
      raw.replaceAll(RegExp(r'[^0-9]'), '');

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDay,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
      locale: const Locale('es', 'PE'),
    );
    if (picked == null || !mounted) return;
    setState(() => _selectedDay = picked);
    await _loadData();
  }

  List<BitacoraCampoEntry> get _visible {
    var list = _entries;
    final q = _localQuery.trim();
    final dniQ = _digitsOnly(q);
    if (q.isNotEmpty && dniQ.length < 7) {
      list = list
          .where((e) => BitacoraCampoEntry.matchesLocalQuery(e, q))
          .toList();
    }
    return list;
  }

  List<DropdownMenuItem<String?>> get _sectionOptions {
    final seen = <String>{};
    final items = <DropdownMenuItem<String?>>[
      const DropdownMenuItem<String?>(value: null, child: Text('Todas')),
    ];
    for (final e in _entries) {
      final key = e.seccionKey.trim();
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
    final visible = _visible;
    final ubicaciones = visible.where((e) => e.isUbicacion).length;
    final telegram = visible.where((e) => e.isTelegram).length;
    final telegramOk = visible
        .where((e) => e.isTelegram && (e.payload['estado']?.toString() == 'completado'))
        .length;
    final telegramErr = telegram - telegramOk;
    final notas = visible.where((e) => e.isNota).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Bitácora de campo'),
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
                      Text(
                        'Bitácora del ${_prettyDateFmt.format(_selectedDay)}',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Ubicaciones GPS, consultas Telegram y notas del equipo.',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade600,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _kpiCard('Ubicaciones', '$ubicaciones', Icons.add_location_alt_outlined),
                          _kpiCard(
                            'Telegram',
                            '$telegramOk/$telegram',
                            Icons.travel_explore_outlined,
                          ),
                          _kpiCard('Telegram error', '$telegramErr', Icons.error_outline),
                          _kpiCard('Notas', '$notas', Icons.notes_outlined),
                        ],
                      ),
                      const SizedBox(height: 12),
                      _buildFilters(),
                      const SizedBox(height: 12),
                      if (visible.isEmpty)
                        _buildEmpty()
                      else
                        ...visible.map(_buildEntryTile),
                    ],
                  ),
                ),
    );
  }

  Widget _buildFilters() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _tipoChip('todos', 'Todos'),
                _tipoChip(BitacoraCampoEntry.tipoUbicacion, 'Ubicaciones'),
                _tipoChip(BitacoraCampoEntry.tipoTelegram, 'Telegram'),
                _tipoChip('notas', 'Notas'),
              ],
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                isDense: true,
                labelText: 'Buscar (DNI, nombre, código…)',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _localQuery.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          _loadData();
                        },
                      ),
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _loadData(),
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String?>(
              value: _sectionFilter,
              decoration: const InputDecoration(
                labelText: 'Sección',
                isDense: true,
              ),
              items: _sectionOptions,
              onChanged: (value) async {
                setState(() => _sectionFilter = value);
                await _loadData();
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _tipoChip(String value, String label) {
    final selected = _tipoFilter == value;
    return FilterChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) async {
        setState(() => _tipoFilter = value);
        await _loadData();
      },
      selectedColor: AppTheme.primaryColor.withValues(alpha: 0.18),
      checkmarkColor: AppTheme.primaryColor,
    );
  }

  Widget _kpiCard(String label, String value, IconData icon) {
    return SizedBox(
      width: 150,
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(icon, size: 18, color: AppTheme.primaryColor),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      value,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 16,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      label,
                      style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEntryTile(BitacoraCampoEntry entry) {
    final icon = switch (entry.tipo) {
      BitacoraCampoEntry.tipoUbicacion => Icons.add_location_alt_outlined,
      BitacoraCampoEntry.tipoTelegram => Icons.travel_explore_outlined,
      BitacoraCampoEntry.tipoNotaCampo => Icons.sticky_note_2_outlined,
      BitacoraCampoEntry.tipoNotaGestion => Icons.assignment_outlined,
      _ => Icons.event_note_outlined,
    };
    final color = switch (entry.tipo) {
      BitacoraCampoEntry.tipoUbicacion => AppTheme.success,
      BitacoraCampoEntry.tipoTelegram => AppTheme.info,
      BitacoraCampoEntry.tipoNotaCampo => AppTheme.primaryColor,
      BitacoraCampoEntry.tipoNotaGestion => Colors.deepOrange,
      _ => Colors.grey,
    };
    final time = entry.creadoAt != null ? _timeFmt.format(entry.creadoAt!) : '—';
    final title = entry.clienteNombre.isNotEmpty
        ? entry.clienteNombre
        : (entry.dni.isNotEmpty ? 'DNI ${entry.dni}' : 'Sin cliente');

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _onTapEntry(entry),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                backgroundColor: color.withValues(alpha: 0.15),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            style: const TextStyle(fontWeight: FontWeight.w700),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Text(
                          time,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      [
                        entry.displayType,
                        if (entry.dni.isNotEmpty) 'DNI ${entry.dni}',
                        if (entry.seccionKey.isNotEmpty)
                          sectionDisplayLabel(entry.seccionKey),
                      ].join(' · '),
                      style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      entry.resumen,
                      style: const TextStyle(fontSize: 13),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (entry.usuarioNombre.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        entry.usuarioNombre,
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade500,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openClient(BitacoraCampoEntry entry) async {
    if (!entry.hasCliente ||
        entry.campaignId.isEmpty ||
        entry.seccionKey.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Este evento no tiene ficha de cliente.')),
      );
      return;
    }
    final client = await _firestore.getClient(
      campaignId: entry.campaignId,
      section: entry.seccionKey,
      clientId: entry.clienteId,
    );
    if (!mounted) return;
    if (client == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No se encontró el cliente en la campaña.')),
      );
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ClientDetailScreen(
          client: client,
          campaignId: entry.campaignId,
          section: entry.seccionKey,
        ),
      ),
    );
  }

  Future<void> _onTapEntry(BitacoraCampoEntry entry) async {
    if (entry.isTelegram) {
      await _showTelegramSheet(entry);
      return;
    }
    if (entry.isUbicacion) {
      await _showUbicacionSheet(entry);
      return;
    }
    await _openClient(entry);
  }

  Future<void> _showUbicacionSheet(BitacoraCampoEntry entry) async {
    final lat = (entry.payload['lat'] as num?)?.toDouble();
    final lng = (entry.payload['lng'] as num?)?.toDouble();
    final latAnt = (entry.payload['lat_anterior'] as num?)?.toDouble();
    final lngAnt = (entry.payload['lng_anterior'] as num?)?.toDouble();
    final mapsUrl = entry.payload['maps_url']?.toString() ??
        (lat != null && lng != null
            ? 'https://www.google.com/maps?q=$lat,$lng'
            : '');

    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                entry.clienteNombre.isNotEmpty
                    ? entry.clienteNombre
                    : 'Ubicación GPS',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(entry.resumen),
              if (latAnt != null && lngAnt != null) ...[
                const SizedBox(height: 8),
                Text(
                  'Anterior: ${latAnt.toStringAsFixed(5)}, ${lngAnt.toStringAsFixed(5)}',
                  style: TextStyle(color: Colors.grey.shade700),
                ),
              ],
              if (lat != null && lng != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Nueva: ${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
              const SizedBox(height: 16),
              if (mapsUrl.isNotEmpty)
                FilledButton.icon(
                  onPressed: () async {
                    final uri = Uri.parse(mapsUrl);
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  },
                  icon: const Icon(Icons.map_outlined),
                  label: const Text('Abrir en Maps'),
                ),
              if (entry.hasCliente) ...[
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    _openClient(entry);
                  },
                  child: const Text('Ver ficha del cliente'),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Future<void> _showTelegramSheet(BitacoraCampoEntry entry) async {
    final jobId = entry.payload['job_id']?.toString() ?? entry.origenId;
    if (!mounted) return;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.55,
          minChildSize: 0.35,
          maxChildSize: 0.9,
          builder: (_, scrollController) {
            return StreamBuilder(
              stream: jobId.isEmpty ? null : _doxeo.streamJob(jobId),
              builder: (context, snap) {
                final job = snap.data;
                final estado = job?.estado ??
                    entry.payload['estado']?.toString() ??
                    '—';
                final raw = job?.raw ?? '';
                final errorMsg = job?.errorMsg ??
                    entry.payload['error_msg']?.toString() ??
                    '';
                final imagenes = job?.imagenes ?? const <String>[];
                final archivos = job?.archivos ?? const <DoxeoArchivo>[];

                return ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
                  children: [
                    Text(
                      entry.payload['comando_nombre']?.toString() ?? 'Telegram',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text('Estado: $estado · DNI ${entry.dni}'),
                    if (entry.usuarioNombre.isNotEmpty)
                      Text(
                        'Solicitó: ${entry.usuarioNombre}',
                        style: TextStyle(color: Colors.grey.shade600),
                      ),
                    const SizedBox(height: 12),
                    if (errorMsg.isNotEmpty)
                      Text(
                        errorMsg,
                        style: const TextStyle(color: AppTheme.danger),
                      ),
                    if (raw.isNotEmpty)
                      SelectableText(
                        raw.length > 4000 ? '${raw.substring(0, 4000)}…' : raw,
                        style: const TextStyle(fontSize: 13, height: 1.35),
                      )
                    else if (snap.connectionState == ConnectionState.waiting)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else
                      Text(
                        entry.resumen,
                        style: TextStyle(color: Colors.grey.shade700),
                      ),
                    if (imagenes.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      const Text(
                        'Imágenes',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      ...imagenes.take(6).map((path) {
                        return FutureBuilder<String>(
                          future: _doxeo.resolveImageUrl(path),
                          builder: (context, imgSnap) {
                            final url = imgSnap.data;
                            if (url == null || url.isEmpty) {
                              return const SizedBox.shrink();
                            }
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: Image.network(
                                  url,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) =>
                                      const SizedBox.shrink(),
                                ),
                              ),
                            );
                          },
                        );
                      }),
                    ],
                    if (archivos.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      const Text(
                        'Documentos',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 4),
                      ...archivos.map((archivo) {
                        final name = archivo.fileName.isNotEmpty
                            ? archivo.fileName
                            : 'documento.pdf';
                        return ListTile(
                          contentPadding: EdgeInsets.zero,
                          dense: true,
                          leading: const Icon(
                            Icons.picture_as_pdf,
                            color: AppTheme.danger,
                          ),
                          title: Text(name, maxLines: 2),
                          subtitle: const Text('Toca para abrir'),
                          trailing: const Icon(Icons.open_in_new, size: 18),
                          onTap: () async {
                            try {
                              await _doxeo.openArchivo(archivo);
                            } catch (e) {
                              if (!context.mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('No se pudo abrir el PDF: $e'),
                                  backgroundColor: AppTheme.danger,
                                ),
                              );
                            }
                          },
                        );
                      }),
                    ],
                    if (entry.hasCliente) ...[
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: () {
                          Navigator.pop(ctx);
                          _openClient(entry);
                        },
                        child: const Text('Ver ficha del cliente'),
                      ),
                    ],
                  ],
                );
              },
            );
          },
        );
      },
    );
  }

  Widget _buildEmpty() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Column(
        children: [
          Icon(Icons.inbox_outlined, size: 48, color: Colors.grey.shade400),
          const SizedBox(height: 12),
          const Text(
            'Aún no hay novedades este día',
            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          Text(
            'Los eventos anteriores al deploy aparecen tras el backfill.\n'
            'Las ubicaciones, Telegram y notas nuevas se listan aquí al instante.',
            style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 40, color: AppTheme.danger),
            const SizedBox(height: 12),
            Text(
              'No se pudo cargar la bitácora.\n$_error',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            FilledButton(onPressed: _loadData, child: const Text('Reintentar')),
          ],
        ),
      ),
    );
  }
}
