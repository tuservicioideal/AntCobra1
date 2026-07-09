import 'package:flutter/material.dart';

import '../utils/section_utils.dart';
import '../utils/territorial_utils.dart';

typedef TerritorialSelectionCallback = void Function({
  required String compositeKey,
  required String region,
  required String zona,
  required String seccionLetter,
});

/// Cascade picker: Región → Zona → Sección, filtered by active campaign sections.
class TerritorialSectionPicker extends StatefulWidget {
  final Map<String, dynamic> catalog;
  final List<String> availableSectionKeys;
  final String initialCompositeKey;
  final bool allowUnassigned;
  final TerritorialSelectionCallback onSelectionChanged;

  const TerritorialSectionPicker({
    super.key,
    required this.catalog,
    required this.availableSectionKeys,
    required this.onSelectionChanged,
    this.initialCompositeKey = '',
    this.allowUnassigned = true,
  });

  @override
  State<TerritorialSectionPicker> createState() =>
      _TerritorialSectionPickerState();
}

class _TerritorialSectionPickerState extends State<TerritorialSectionPicker> {
  static const _unassigned = '__unassigned__';

  String _region = '';
  String _zona = '';
  String _seccion = '';

  final _manualRegionCtrl = TextEditingController();
  final _manualZonaCtrl = TextEditingController();
  final _manualSeccionCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _applyInitialKey(widget.initialCompositeKey);
    WidgetsBinding.instance.addPostFrameCallback((_) => _notifySelection());
  }

  @override
  void didUpdateWidget(TerritorialSectionPicker oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialCompositeKey != widget.initialCompositeKey) {
      _applyInitialKey(widget.initialCompositeKey);
      _notifySelection();
    }
  }

  @override
  void dispose() {
    _manualRegionCtrl.dispose();
    _manualZonaCtrl.dispose();
    _manualSeccionCtrl.dispose();
    super.dispose();
  }

  void _applyInitialKey(String key) {
    if (key.isEmpty) {
      _region = '';
      _zona = '';
      _seccion = '';
      return;
    }

    final parts = parseCompositeSectionKey(key);
    if (parts == null) return;

    _region = parts.region;
    _zona = parts.zona;
    _seccion = parts.seccionLetter;

    if (!_regionOptions.contains(_region)) {
      _region = '';
      _zona = '';
      _seccion = '';
      return;
    }
    if (!_zonaOptionsFor(_region).contains(_zona)) {
      _zona = '';
      _seccion = '';
      return;
    }
    if (!_seccionOptionsFor(_region, _zona).contains(_seccion)) {
      _seccion = '';
    }
  }

  bool _isSectionAvailable(String region, String zona, String seccion) {
    final key = buildCompositeSectionKey(region, zona, seccion);
    if (key.isEmpty) return false;
    if (widget.availableSectionKeys.isEmpty) return true;
    return widget.availableSectionKeys.contains(key);
  }

  List<String> get _regionOptions {
    if (widget.catalog.isEmpty) return [];

    final regions = widget.catalog.keys.toList()..sort();
    return regions.where((region) {
      final zonas = widget.catalog[region];
      if (zonas is! Map<String, dynamic>) return false;
      final zonasMap = zonas['zonas'];
      if (zonasMap is! Map<String, dynamic>) return false;

      for (final zonaEntry in zonasMap.entries) {
        final secciones = (zonaEntry.value as Map<String, dynamic>?)?['secciones'];
        if (secciones is! List) continue;
        for (final sec in secciones) {
          if (_isSectionAvailable(region, zonaEntry.key, sec.toString())) {
            return true;
          }
        }
      }
      return false;
    }).toList();
  }

  List<String> _zonaOptionsFor(String region) {
    final regionData = widget.catalog[region];
    if (regionData is! Map<String, dynamic>) return [];

    final zonasMap = regionData['zonas'];
    if (zonasMap is! Map<String, dynamic>) return [];

    final zonas = zonasMap.keys.toList()..sort();
    return zonas.where((zona) {
      final secciones =
          (zonasMap[zona] as Map<String, dynamic>?)?['secciones'] as List?;
      if (secciones == null) return false;
      for (final sec in secciones) {
        if (_isSectionAvailable(region, zona, sec.toString())) return true;
      }
      return false;
    }).toList();
  }

  List<String> _seccionOptionsFor(String region, String zona) {
    final regionData = widget.catalog[region];
    if (regionData is! Map<String, dynamic>) return [];

    final zonasMap = regionData['zonas'];
    if (zonasMap is! Map<String, dynamic>) return [];

    final zonaData = zonasMap[zona];
    if (zonaData is! Map<String, dynamic>) return [];

    final raw = zonaData['secciones'];
    if (raw is! List) return [];

    final secciones = raw.map((e) => e.toString().trim().toUpperCase()).toList()
      ..sort();
    return secciones
        .where((sec) => _isSectionAvailable(region, zona, sec))
        .toList();
  }

  void _notifySelection() {
    if (_region.isEmpty || _zona.isEmpty || _seccion.isEmpty) {
      widget.onSelectionChanged(
        compositeKey: '',
        region: '',
        zona: '',
        seccionLetter: '',
      );
      return;
    }

    final compositeKey =
        buildCompositeSectionKey(_region, _zona, _seccion);
    widget.onSelectionChanged(
      compositeKey: compositeKey,
      region: _region,
      zona: _zona,
      seccionLetter: _seccion,
    );
  }

  void _setRegion(String? value) {
    if (value == null || value == _unassigned) {
      setState(() {
        _region = '';
        _zona = '';
        _seccion = '';
      });
    } else {
      setState(() {
        _region = value;
        _zona = '';
        _seccion = '';
        final zonas = _zonaOptionsFor(_region);
        if (zonas.isNotEmpty) {
          _zona = zonas.first;
          final secs = _seccionOptionsFor(_region, _zona);
          _seccion = secs.isNotEmpty ? secs.first : '';
        }
      });
    }
    _notifySelection();
  }

  void _setZona(String? value) {
    if (value == null) return;
    setState(() {
      _zona = value;
      _seccion = '';
      final secs = _seccionOptionsFor(_region, _zona);
      if (secs.isNotEmpty) _seccion = secs.first;
    });
    _notifySelection();
  }

  void _setSeccion(String? value) {
    if (value == null) return;
    setState(() => _seccion = value);
    _notifySelection();
  }

  void _applyManual() {
    final region = _manualRegionCtrl.text.trim();
    final zona = _manualZonaCtrl.text.trim();
    final seccion = _manualSeccionCtrl.text.trim().toUpperCase();
    if (region.isEmpty || zona.isEmpty || seccion.isEmpty) return;

    setState(() {
      _region = region;
      _zona = zona;
      _seccion = seccion;
    });
    _notifySelection();
  }

  @override
  Widget build(BuildContext context) {
    final regions = _regionOptions;
    final catalogEmpty = widget.catalog.isEmpty;
    final zonas = _region.isNotEmpty ? _zonaOptionsFor(_region) : <String>[];
    final secciones =
        (_region.isNotEmpty && _zona.isNotEmpty)
            ? _seccionOptionsFor(_region, _zona)
            : <String>[];

    final regionValue = _region.isEmpty
        ? (widget.allowUnassigned ? _unassigned : null)
        : (regions.contains(_region) ? _region : null);
    final zonaValue =
        _zona.isNotEmpty && zonas.contains(_zona) ? _zona : null;
    final seccionValue =
        _seccion.isNotEmpty && secciones.contains(_seccion) ? _seccion : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (catalogEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'Catálogo vacío. Suba y distribuya un Excel desde admin-app.',
              style: TextStyle(fontSize: 12, color: Colors.orange.shade800),
            ),
          )
        else if (regions.isEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'No hay secciones de campaña que coincidan con el catálogo.',
              style: TextStyle(fontSize: 12, color: Colors.orange.shade800),
            ),
          )
        else
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              '${regions.length} regiones disponibles en campaña activa',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
            ),
          ),
        DropdownButtonFormField<String>(
          value: catalogEmpty ? null : regionValue,
          decoration: const InputDecoration(
            labelText: 'Región',
            prefixIcon: Icon(Icons.public_outlined, size: 20),
          ),
          items: [
            if (widget.allowUnassigned)
              const DropdownMenuItem(
                value: _unassigned,
                child: Text('Sin asignar'),
              ),
            ...regions.map(
              (r) => DropdownMenuItem(value: r, child: Text('Región $r')),
            ),
          ],
          onChanged: catalogEmpty ? null : _setRegion,
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          value: zonaValue,
          decoration: const InputDecoration(
            labelText: 'Zona',
            prefixIcon: Icon(Icons.map_outlined, size: 20),
          ),
          items: zonas
              .map((z) => DropdownMenuItem(value: z, child: Text('Zona $z')))
              .toList(),
          onChanged: _region.isEmpty || catalogEmpty ? null : _setZona,
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          value: seccionValue,
          decoration: const InputDecoration(
            labelText: 'Sección',
            prefixIcon: Icon(Icons.folder_outlined, size: 20),
          ),
          items: secciones
              .map(
                (s) => DropdownMenuItem(
                  value: s,
                  child: Text(
                    sectionDisplayLabel(
                      buildCompositeSectionKey(_region, _zona, s),
                    ),
                  ),
                ),
              )
              .toList(),
          onChanged:
              _region.isEmpty || _zona.isEmpty || catalogEmpty ? null : _setSeccion,
        ),
        if (_region.isNotEmpty && _zona.isNotEmpty && _seccion.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            'Selección: ${sectionDisplayLabel(buildCompositeSectionKey(_region, _zona, _seccion))}',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade700,
            ),
          ),
        ],
        const SizedBox(height: 12),
        Text(
          'O ingresa manualmente:',
          style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _manualRegionCtrl,
                decoration: const InputDecoration(
                  labelText: 'Región',
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: TextField(
                controller: _manualZonaCtrl,
                decoration: const InputDecoration(
                  labelText: 'Zona',
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: TextField(
                controller: _manualSeccionCtrl,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  labelText: 'Sec.',
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 4),
            IconButton(
              onPressed: _applyManual,
              tooltip: 'Aplicar manual',
              icon: const Icon(Icons.check_circle_outline),
              color: Theme.of(context).colorScheme.primary,
            ),
          ],
        ),
      ],
    );
  }
}
