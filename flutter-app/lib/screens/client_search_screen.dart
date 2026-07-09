import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../models/client_model.dart';
import '../services/campana_banco_filter_notifier.dart';
import '../services/campaign_service.dart';
import '../services/campaign_stats_service.dart';
import '../utils/campana_banco_utils.dart';
import '../utils/client_list_pagination.dart';
import '../utils/contact_metrics_utils.dart';
import '../utils/responsive.dart';
import '../widgets/client_list_tile.dart';
import '../widgets/client_list_pagination_bar.dart';
import '../widgets/master_detail_scaffold.dart';
import 'client_detail_screen.dart';

class ClientSearchScreen extends StatefulWidget {
  const ClientSearchScreen({super.key});

  @override
  State<ClientSearchScreen> createState() => _ClientSearchScreenState();
}

class _ClientSearchScreenState extends State<ClientSearchScreen> {
  final _searchController = TextEditingController();
  final _statsService = CampaignStatsService();
  final _campaignService = CampaignService();
  final _pagination = ClientListPagination();

  List<ClientModel> _allClients = [];
  bool _loading = false;
  bool _loadedOnce = false;
  String _query = '';
  String? _campaignId;
  String? _selectedClientId;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _searchController.addListener(_onSearchChanged);
    _initCampaignId();
  }

  Future<void> _initCampaignId() async {
    final campaignId = await _campaignService.getActiveCampaignId();
    if (mounted) setState(() => _campaignId = campaignId);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.removeListener(_onSearchChanged);
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _ensureClientsLoaded() async {
    if (_loadedOnce || _loading) return;
    final campaignId = _campaignId ?? await _campaignService.getActiveCampaignId();
    if (campaignId == null) {
      if (mounted) setState(() => _loading = false);
      return;
    }

    setState(() => _loading = true);
    final clients = await _statsService.loadActiveClients(campaignId: campaignId);
    if (mounted) {
      setState(() {
        _campaignId = campaignId;
        _allClients = clients;
        _loading = false;
        _loadedOnce = true;
      });
    }
  }

  void _onSearchChanged() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      if (!mounted) return;
      final next = _searchController.text.trim();
      if (next.length >= 2 && !_loadedOnce) {
        await _ensureClientsLoaded();
      }
      if (mounted) {
        setState(() {
          _query = next;
          _pagination.reset();
          _selectedClientId = null;
        });
      }
    });
  }

  List<ClientModel> _filteredResults(String? campanaFilter) {
    if (_query.length < 2) return [];

    final results = applyCampanaBancoFilter(_allClients, campanaFilter)
        .where((c) => clientMatchesSearchQuery(c, _query))
        .toList()
      ..sort((a, b) => a.displayName.compareTo(b.displayName));
    return results;
  }

  void _openClient(ClientModel client) {
    if (_campaignId == null) return;
    if (context.isExpanded) {
      setState(() => _selectedClientId = client.id);
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ClientDetailScreen(
          client: client,
          campaignId: _campaignId!,
          section: client.seccionKey.isNotEmpty
              ? client.seccionKey
              : client.seccion,
        ),
      ),
    );
  }

  Widget _buildResultsHeader(int count) {
    if (_query.length < 2) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Text(
        '$count resultado${count == 1 ? '' : 's'}'
        '${_pagination.needsBar ? ' · pág. ${_pagination.page + 1}/${_pagination.totalPages}' : ''}',
        style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
      ),
    );
  }

  Widget _buildResultsList({
    required List<ClientModel> pageResults,
    required bool showFilterBar,
    required String? campanaFilter,
  }) {
    if (_query.length < 2) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.search, size: 48, color: Colors.grey.shade400),
              const SizedBox(height: 12),
              Text(
                'Escribe al menos 2 caracteres',
                style: TextStyle(color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
      );
    }

    if (pageResults.isEmpty) {
      return Center(
        child: Text(
          'Sin coincidencias',
          style: TextStyle(color: Colors.grey.shade600),
        ),
      );
    }

    return ListView.builder(
      itemCount: pageResults.length,
      itemBuilder: (context, index) {
        final client = pageResults[index];
        return ClientListTile(
          client: client,
          isSelected: _selectedClientId == client.id,
          showChevron: !context.isExpanded,
          showCampanaBadge: showFilterBar && campanaFilter == null,
          onTap: () => _openClient(client),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final campanaFilter = context.watch<CampanaBancoFilterNotifier>().selected;
    final results = _filteredResults(campanaFilter);
    final pageResults = _pagination.slice(results);
    final showFilterBar =
        context.watch<CampanaBancoFilterNotifier>().showFilterBar;

    ClientModel? selectedClient;
    if (_selectedClientId != null) {
      final matches = results.where((c) => c.id == _selectedClientId);
      if (matches.isNotEmpty) selectedClient = matches.first;
    }

    final searchField = TextField(
      controller: _searchController,
      autofocus: !context.isExpanded,
      style: const TextStyle(color: Colors.white, fontSize: 16),
      decoration: InputDecoration(
        hintText: 'Nombre, DNI, código o teléfono…',
        hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.6)),
        border: InputBorder.none,
        suffixIcon: _query.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.clear, color: Colors.white70),
                tooltip: 'Limpiar búsqueda',
                onPressed: () {
                  _searchController.clear();
                  setState(() {
                    _query = '';
                    _selectedClientId = null;
                    _pagination.reset();
                  });
                },
              )
            : null,
      ),
    );

    final listBody = _loading
        ? const Center(
            child: CircularProgressIndicator(color: AppTheme.primaryColor),
          )
        : _buildResultsList(
            pageResults: pageResults,
            showFilterBar: showFilterBar,
            campanaFilter: campanaFilter,
          );

    return Scaffold(
      appBar: AppBar(title: searchField),
      body: context.isExpanded
          ? MasterDetailScaffold(
              header: _buildResultsHeader(results.length),
              master: Column(
                children: [
                  Expanded(child: listBody),
                  ClientListPaginationBar(
                    pagination: _pagination,
                    onPageChanged: (page) =>
                        setState(() => _pagination.goTo(page)),
                  ),
                ],
              ),
              detail: selectedClient == null || _campaignId == null
                  ? null
                  : ClientDetailScreen(
                      key: ValueKey(selectedClient.id),
                      client: selectedClient,
                      campaignId: _campaignId!,
                      section: selectedClient.seccionKey.isNotEmpty
                          ? selectedClient.seccionKey
                          : selectedClient.seccion,
                      embedded: true,
                    ),
              emptyDetail: const MasterDetailEmptyPlaceholder(
                icon: Icons.search,
                title: 'Selecciona un resultado',
                subtitle: 'Busca y elige un cliente para ver su ficha aquí.',
              ),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildResultsHeader(results.length),
                Expanded(child: listBody),
                ClientListPaginationBar(
                  pagination: _pagination,
                  onPageChanged: (page) =>
                      setState(() => _pagination.goTo(page)),
                ),
              ],
            ),
    );
  }
}
