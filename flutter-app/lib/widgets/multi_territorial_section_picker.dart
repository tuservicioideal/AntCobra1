import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../utils/territorial_utils.dart';
import 'territorial_section_picker.dart';

/// Multi-select territorial sections with chips + hierarchy tree
/// (mirrors admin-app TeamPage).
class MultiTerritorialSectionPicker extends StatefulWidget {
  final Map<String, dynamic> catalog;
  final List<String> availableSectionKeys;
  final List<String> initialSecciones;
  final ValueChanged<List<String>> onSeccionesChanged;

  const MultiTerritorialSectionPicker({
    super.key,
    required this.catalog,
    required this.availableSectionKeys,
    required this.onSeccionesChanged,
    this.initialSecciones = const [],
  });

  @override
  State<MultiTerritorialSectionPicker> createState() =>
      _MultiTerritorialSectionPickerState();
}

class _MultiTerritorialSectionPickerState
    extends State<MultiTerritorialSectionPicker> {
  late List<String> _selectedKeys;
  String _pendingKey = '';

  @override
  void initState() {
    super.initState();
    _selectedKeys = List<String>.from(widget.initialSecciones);
    // Do not notify the parent on init. Emitting a new List instance here
    // makes parents that store it and rebuild (e.g. StatefulBuilder dialogs)
    // see `initialSecciones !=` forever and freeze the UI.
  }

  @override
  void didUpdateWidget(MultiTerritorialSectionPicker oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!listEquals(oldWidget.initialSecciones, widget.initialSecciones)) {
      _selectedKeys = List<String>.from(widget.initialSecciones);
      // Sync from parent only; do not re-emit — parent already owns this value.
    }
  }

  void _notify() {
    widget.onSeccionesChanged(List<String>.from(_selectedKeys));
  }

  void _setKeys(List<String> keys) {
    setState(() {
      _selectedKeys = List<String>.from(keys)..sort();
    });
    _notify();
  }

  void _addPending() {
    final key = _pendingKey.trim();
    if (key.isEmpty) return;
    if (_selectedKeys.contains(key)) return;
    _setKeys([..._selectedKeys, key]);
    setState(() => _pendingKey = '');
  }

  Future<void> _confirmAndApply({
    required int count,
    required String label,
    required List<String> nextKeys,
  }) async {
    if (count > 1) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Quitar territorio'),
          content: Text('Se quitarán $count secciones de $label.\n¿Continuar?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Quitar'),
            ),
          ],
        ),
      );
      if (ok != true || !mounted) return;
    }
    _setKeys(nextKeys);
  }

  String _chipLabel(String key) {
    final parts = parseCompositeSectionKey(key);
    if (parts != null) {
      return 'R${parts.region} Z${parts.zona} S${parts.seccionLetter}';
    }
    return key;
  }

  Widget _buildHierarchyTree() {
    final hierarchy = groupSeccionesByHierarchy(_selectedKeys);
    if (hierarchy.isEmpty) {
      return Text(
        'Ningún territorio compuesto asignado',
        style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final regionEntry in hierarchy.entries) ...[
          Row(
            children: [
              Expanded(
                child: Text(
                  'Región ${regionEntry.key}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
              TextButton(
                onPressed: () {
                  final n = countSeccionesInRegion(
                    _selectedKeys,
                    regionEntry.key,
                  );
                  _confirmAndApply(
                    count: n,
                    label: 'la región ${regionEntry.key}',
                    nextKeys: removeRegion(_selectedKeys, regionEntry.key),
                  );
                },
                style: TextButton.styleFrom(
                  foregroundColor: Colors.red.shade700,
                  visualDensity: VisualDensity.compact,
                ),
                child: const Text('Quitar región'),
              ),
            ],
          ),
          for (final zonaEntry in regionEntry.value.entries) ...[
            Padding(
              padding: const EdgeInsets.only(left: 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Zona ${zonaEntry.key}',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                        color: Colors.grey.shade800,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: () {
                      final n = countSeccionesInZona(
                        _selectedKeys,
                        regionEntry.key,
                        zonaEntry.key,
                      );
                      _confirmAndApply(
                        count: n,
                        label: 'la zona ${regionEntry.key}/${zonaEntry.key}',
                        nextKeys: removeZona(
                          _selectedKeys,
                          regionEntry.key,
                          zonaEntry.key,
                        ),
                      );
                    },
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.orange.shade800,
                      visualDensity: VisualDensity.compact,
                    ),
                    child: const Text('Quitar zona'),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(left: 24, bottom: 6),
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                children: zonaEntry.value.map((key) {
                  final parts = parseCompositeSectionKey(key);
                  final letter = parts?.seccionLetter ?? key;
                  return InputChip(
                    label: Text(letter, style: const TextStyle(fontSize: 11)),
                    deleteIcon: const Icon(Icons.close, size: 16),
                    onDeleted: () => _setKeys(removeSeccion(_selectedKeys, key)),
                  );
                }).toList(),
              ),
            ),
          ],
        ],
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(),
        const SizedBox(height: 4),
        Text(
          'Secciones asignadas',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
              ),
        ),
        const SizedBox(height: 8),
        TerritorialSectionPicker(
          catalog: widget.catalog,
          availableSectionKeys: widget.availableSectionKeys,
          initialCompositeKey: _pendingKey,
          allowUnassigned: true,
          onSelectionChanged: ({
            required compositeKey,
            required region,
            required zona,
            required seccionLetter,
          }) {
            if (_pendingKey == compositeKey) return;
            setState(() => _pendingKey = compositeKey);
          },
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
            onPressed: _pendingKey.isEmpty ? null : _addPending,
            icon: const Icon(Icons.add, size: 18),
            label: const Text('Agregar sección'),
            style: FilledButton.styleFrom(
              visualDensity: VisualDensity.compact,
            ),
          ),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.grey.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.grey.shade200),
          ),
          child: _selectedKeys.isEmpty
              ? Text(
                  'Ninguna sección seleccionada',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                )
              : Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: _selectedKeys.map((key) {
                    return InputChip(
                      label: Text(
                        _chipLabel(key),
                        style: const TextStyle(fontSize: 11),
                      ),
                      deleteIcon: const Icon(Icons.close, size: 16),
                      onDeleted: () =>
                          _setKeys(removeSeccion(_selectedKeys, key)),
                    );
                  }).toList(),
                ),
        ),
        const SizedBox(height: 10),
        Text(
          'Territorio asignado',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          'Quitar territorio no mueve clientes; solo deja de asignar esa zona/sección al gestor.',
          style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.grey.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.grey.shade200),
          ),
          child: _buildHierarchyTree(),
        ),
      ],
    );
  }
}
