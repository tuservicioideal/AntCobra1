import 'package:flutter/material.dart';

import '../models/client_model.dart';
import '../utils/client_list_pagination.dart';
import 'client_list_pagination_bar.dart';

/// Searchable, paginated checkbox list for bulk client selection dialogs.
class PaginatedClientCheckboxList extends StatefulWidget {
  const PaginatedClientCheckboxList({
    super.key,
    required this.clients,
    required this.selected,
    required this.onSelectionChanged,
    this.enabled = true,
    this.height = 280,
  });

  final List<ClientModel> clients;
  final Set<String> selected;
  final void Function(Set<String> selected) onSelectionChanged;
  final bool enabled;
  final double height;

  @override
  State<PaginatedClientCheckboxList> createState() =>
      _PaginatedClientCheckboxListState();
}

class _PaginatedClientCheckboxListState
    extends State<PaginatedClientCheckboxList> {
  final _searchController = TextEditingController();
  final _pagination = ClientListPagination();
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<ClientModel> get _filtered {
    if (_query.isEmpty) return widget.clients;
    return widget.clients
        .where((c) => matchesClientSearch(c, _query))
        .toList();
  }

  void _onSearchChanged(String value) {
    setState(() {
      _query = value;
      _pagination.reset();
    });
  }

  void _toggle(String id, bool? checked) {
    final next = Set<String>.from(widget.selected);
    if (checked == true) {
      next.add(id);
    } else {
      next.remove(id);
    }
    widget.onSelectionChanged(next);
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;
    final pageItems = _pagination.slice(filtered);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _searchController,
          enabled: widget.enabled,
          decoration: InputDecoration(
            hintText: 'Buscar por nombre, DNI o código…',
            prefixIcon: const Icon(Icons.search, size: 20),
            suffixIcon: _query.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear, size: 18),
                    onPressed: widget.enabled
                        ? () {
                            _searchController.clear();
                            _onSearchChanged('');
                          }
                        : null,
                  )
                : null,
            isDense: true,
            border: const OutlineInputBorder(),
          ),
          onChanged: _onSearchChanged,
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: widget.height,
          child: filtered.isEmpty
              ? Center(
                  child: Text(
                    _query.isNotEmpty
                        ? 'Sin coincidencias'
                        : 'No hay clientes',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                )
              : ListView.builder(
                  itemCount: pageItems.length,
                  itemBuilder: (_, index) {
                    final c = pageItems[index];
                    return CheckboxListTile(
                      dense: true,
                      value: widget.selected.contains(c.id),
                      onChanged: widget.enabled
                          ? (v) => _toggle(c.id, v)
                          : null,
                      title: Text(
                        c.displayName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text('DNI: ${c.numeroDocumento}'),
                    );
                  },
                ),
        ),
        ClientListPaginationBar(
          pagination: _pagination,
          onPageChanged: (page) => setState(() => _pagination.goTo(page)),
        ),
      ],
    );
  }
}
