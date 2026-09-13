import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../services/map_visit_candidates_notifier.dart';
import '../services/shell_tab_intent_notifier.dart';
import '../utils/client_list_pagination.dart';
import '../utils/section_utils.dart';
import '../widgets/client_list_pagination_bar.dart';
import '../widgets/client_list_tile.dart';

enum _SectionClientStatusFilter { all, pending, managed }

/// Multi-selección de clientes de una sección para enviarlos al tab Mapa.
class SectionClientsPickerScreen extends StatefulWidget {
  const SectionClientsPickerScreen({
    super.key,
    required this.sectionKey,
    required this.clients,
    this.canSendToMap = false,
  });

  final String sectionKey;
  final List<ClientModel> clients;
  final bool canSendToMap;

  @override
  State<SectionClientsPickerScreen> createState() =>
      _SectionClientsPickerScreenState();
}

class _SectionClientsPickerScreenState extends State<SectionClientsPickerScreen> {
  final _searchController = TextEditingController();
  final _pagination = ClientListPagination();
  final Set<String> _selectedIds = <String>{};

  String _query = '';
  _SectionClientStatusFilter _statusFilter = _SectionClientStatusFilter.all;
  bool _onlyWithGps = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<ClientModel> get _visible {
    var list = List<ClientModel>.from(widget.clients);
    switch (_statusFilter) {
      case _SectionClientStatusFilter.pending:
        list = list.where((c) => c.isPendiente).toList();
      case _SectionClientStatusFilter.managed:
        list = list.where((c) => !c.isPendiente).toList();
      case _SectionClientStatusFilter.all:
        break;
    }
    if (_onlyWithGps) {
      list = list.where((c) => c.hasCoordinates).toList();
    }
    if (_query.trim().isNotEmpty) {
      list = list.where((c) => matchesClientSearch(c, _query)).toList();
    }
    list.sort((a, b) {
      final pending = (a.isPendiente ? 0 : 1).compareTo(b.isPendiente ? 0 : 1);
      if (pending != 0) return pending;
      return a.displayName.compareTo(b.displayName);
    });
    return list;
  }

  List<ClientModel> get _selectedClients =>
      widget.clients.where((c) => _selectedIds.contains(c.id)).toList();

  void _toggle(ClientModel client) {
    setState(() {
      if (_selectedIds.contains(client.id)) {
        _selectedIds.remove(client.id);
      } else {
        _selectedIds.add(client.id);
      }
    });
  }

  void _selectPendingWithGps() {
    setState(() {
      _selectedIds
        ..clear()
        ..addAll(
          _visible
              .where((c) => c.isPendiente && c.hasCoordinates)
              .map((c) => c.id),
        );
    });
  }

  void _clearSelection() {
    setState(_selectedIds.clear);
  }

  void _sendToMap() {
    final selected = _selectedClients;
    if (selected.isEmpty || !widget.canSendToMap) return;
    context.read<MapVisitCandidatesNotifier>().addAll(selected);
    context.read<ShellTabIntentNotifier>().goToMap();
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final visible = _visible;
    final pageClients = _pagination.slice(visible);
    final pendingWithGps = widget.clients
        .where((c) => c.isPendiente && c.hasCoordinates)
        .length;
    final withoutGps = widget.clients.where((c) => !c.hasCoordinates).length;

    return Scaffold(
      appBar: AppBar(
        title: Text(sectionDisplayLabel(widget.sectionKey)),
        actions: [
          if (_selectedIds.isNotEmpty)
            TextButton(
              onPressed: _clearSelection,
              child: const Text(
                'Limpiar',
                style: TextStyle(color: Colors.white),
              ),
            ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                hintText: 'Buscar por nombre, DNI o código…',
                prefixIcon: Icon(Icons.search),
                isDense: true,
                border: OutlineInputBorder(),
              ),
              onChanged: (value) => setState(() {
                _query = value;
                _pagination.reset();
              }),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                FilterChip(
                  label: const Text('Todos'),
                  selected: _statusFilter == _SectionClientStatusFilter.all,
                  onSelected: (_) => setState(() {
                    _statusFilter = _SectionClientStatusFilter.all;
                    _pagination.reset();
                  }),
                ),
                FilterChip(
                  label: const Text('Pendientes'),
                  selected: _statusFilter == _SectionClientStatusFilter.pending,
                  onSelected: (_) => setState(() {
                    _statusFilter = _SectionClientStatusFilter.pending;
                    _pagination.reset();
                  }),
                ),
                FilterChip(
                  label: const Text('Ya gestionados'),
                  selected: _statusFilter == _SectionClientStatusFilter.managed,
                  onSelected: (_) => setState(() {
                    _statusFilter = _SectionClientStatusFilter.managed;
                    _pagination.reset();
                  }),
                ),
                FilterChip(
                  label: const Text('Con GPS'),
                  selected: _onlyWithGps,
                  onSelected: (selected) => setState(() {
                    _onlyWithGps = selected;
                    _pagination.reset();
                  }),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    '${visible.length} de ${widget.clients.length} · '
                    '${_selectedIds.length} seleccionados',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                  ),
                ),
                TextButton(
                  onPressed: pendingWithGps == 0 ? null : _selectPendingWithGps,
                  child: const Text('Pendientes con GPS'),
                ),
              ],
            ),
          ),
          if (withoutGps > 0)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '$withoutGps sin ubicación: puedes enviarlos al mapa y '
                  'agregarlos a la ruta desde la lista.',
                  style: TextStyle(fontSize: 11, color: Colors.orange.shade800),
                ),
              ),
            ),
          Expanded(
            child: widget.clients.isEmpty
                ? Center(
                    child: Text(
                      'No hay clientes activos en esta sección.',
                      style: TextStyle(color: Colors.grey.shade600),
                    ),
                  )
                : visible.isEmpty
                    ? Center(
                        child: Text(
                          'Ningún cliente coincide con el filtro.',
                          style: TextStyle(color: Colors.grey.shade600),
                        ),
                      )
                    : ListView.builder(
                        itemCount: pageClients.length,
                        itemBuilder: (context, index) {
                          final client = pageClients[index];
                          final selected = _selectedIds.contains(client.id);
                          return ClientListTile(
                            client: client,
                            isSelected: selected,
                            showChevron: false,
                            distanceLabel: client.hasCoordinates
                                ? 'Con GPS'
                                : 'Sin ubicación',
                            trailing: Icon(
                              selected
                                  ? Icons.check_circle
                                  : Icons.radio_button_unchecked,
                              color: selected
                                  ? AppTheme.primaryColor
                                  : Colors.grey.shade400,
                            ),
                            onTap: () => _toggle(client),
                          );
                        },
                      ),
          ),
          ClientListPaginationBar(
            pagination: _pagination,
            onPageChanged: (page) => setState(() => _pagination.goTo(page)),
          ),
        ],
      ),
      bottomNavigationBar: widget.canSendToMap
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: FilledButton.icon(
                  onPressed: _selectedIds.isEmpty ? null : _sendToMap,
                  icon: const Icon(Icons.map_outlined),
                  label: Text('Enviar a Mapa (${_selectedIds.length})'),
                ),
              ),
            )
          : null,
    );
  }
}
