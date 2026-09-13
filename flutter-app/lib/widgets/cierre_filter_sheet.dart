import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../config/theme.dart';
import '../utils/cierre_filter.dart';
import '../utils/excel_date.dart';
import 'adaptive_sheet.dart';

/// Abre el panel de filtro por fecha de cierre / días restantes.
Future<CierreFilter?> showCierreFilterSheet({
  required BuildContext context,
  required CierreFilter initial,
}) {
  return AdaptiveSheet.show<CierreFilter>(
    context: context,
    title: 'Filtro de cierre',
    builder: (ctx) => _CierreFilterSheetBody(initial: initial),
  );
}

class _CierreFilterSheetBody extends StatefulWidget {
  final CierreFilter initial;

  const _CierreFilterSheetBody({required this.initial});

  @override
  State<_CierreFilterSheetBody> createState() => _CierreFilterSheetBodyState();
}

class _CierreFilterSheetBodyState extends State<_CierreFilterSheetBody> {
  late int _segment; // 0 = Fecha, 1 = Días
  DateTime? _from;
  DateTime? _to;
  int? _maxDias;
  bool _vencidos = false;
  final _daysController = TextEditingController();
  final _dateFmt = DateFormat('dd/MM/yyyy');

  @override
  void initState() {
    super.initState();
    final i = widget.initial;
    if (i.mode == CierreFilterMode.byDate) {
      _segment = 0;
      _from = i.dateFrom;
      _to = i.dateTo;
    } else if (i.mode == CierreFilterMode.byDays) {
      _segment = 1;
      _vencidos = i.vencidos;
      _maxDias = i.maxDias;
      if (!_vencidos && _maxDias != null) {
        _daysController.text = '$_maxDias';
      }
    } else {
      _segment = 1;
      _maxDias = null;
    }
  }

  @override
  void dispose() {
    _daysController.dispose();
    super.dispose();
  }

  Future<void> _pickDate({required bool isFrom}) async {
    final initial = isFrom
        ? (_from ?? DateTime.now())
        : (_to ?? _from ?? DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: dateOnly(initial),
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (isFrom) {
        _from = dateOnly(picked);
        if (_to != null && _to!.isBefore(_from!)) _to = _from;
      } else {
        _to = dateOnly(picked);
        if (_from != null && _to!.isBefore(_from!)) _from = _to;
      }
      _segment = 0;
    });
  }

  void _setPresetDays(int n) {
    setState(() {
      _segment = 1;
      _vencidos = false;
      _maxDias = n;
      _daysController.text = '$n';
    });
  }

  void _setVencidos() {
    setState(() {
      _segment = 1;
      _vencidos = true;
      _maxDias = null;
      _daysController.clear();
    });
  }

  CierreFilter _buildResult() {
    if (_segment == 0) {
      if (_from == null && _to == null) return CierreFilter.none;
      final a = _from ?? _to!;
      final b = _to ?? _from!;
      return CierreFilter.byDateRange(from: a, to: b);
    }
    if (_vencidos) return CierreFilter.onlyVencidos();
    final parsed = int.tryParse(_daysController.text.trim());
    final n = parsed ?? _maxDias;
    if (n == null) return CierreFilter.none;
    return CierreFilter.withinDays(n);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        8,
        16,
        MediaQuery.paddingOf(context).bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(
                value: 0,
                label: Text('Fecha'),
                icon: Icon(Icons.calendar_today_outlined, size: 16),
              ),
              ButtonSegment(
                value: 1,
                label: Text('Días'),
                icon: Icon(Icons.timelapse_outlined, size: 16),
              ),
            ],
            selected: {_segment},
            onSelectionChanged: (s) => setState(() => _segment = s.first),
          ),
          const SizedBox(height: 16),
          if (_segment == 0) _buildDateMode() else _buildDaysMode(),
          const SizedBox(height: 20),
          Row(
            children: [
              TextButton(
                onPressed: () => Navigator.pop(context, CierreFilter.none),
                child: const Text('Limpiar'),
              ),
              const Spacer(),
              FilledButton(
                onPressed: () => Navigator.pop(context, _buildResult()),
                child: const Text('Aplicar'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDateMode() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.event_outlined),
          title: const Text('Desde'),
          subtitle: Text(_from != null ? _dateFmt.format(_from!) : 'Elegir'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _pickDate(isFrom: true),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.event),
          title: const Text('Hasta'),
          subtitle: Text(_to != null ? _dateFmt.format(_to!) : 'Elegir'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _pickDate(isFrom: false),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () async {
              final picked = await showDatePicker(
                context: context,
                initialDate: dateOnly(_from ?? DateTime.now()),
                firstDate: DateTime(2020),
                lastDate: DateTime(2035),
              );
              if (picked == null || !mounted) return;
              setState(() {
                _from = dateOnly(picked);
                _to = dateOnly(picked);
              });
            },
            icon: const Icon(Icons.today_outlined, size: 18),
            label: const Text('Un solo día'),
          ),
        ),
      ],
    );
  }

  Widget _buildDaysMode() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _dayChip('Hoy', selected: !_vencidos && _maxDias == 0, onTap: () => _setPresetDays(0)),
            _dayChip('≤3', selected: !_vencidos && _maxDias == 3, onTap: () => _setPresetDays(3)),
            _dayChip('≤7', selected: !_vencidos && _maxDias == 7, onTap: () => _setPresetDays(7)),
            _dayChip('≤15', selected: !_vencidos && _maxDias == 15, onTap: () => _setPresetDays(15)),
            _dayChip(
              'Ya vencidos',
              selected: _vencidos,
              onTap: _setVencidos,
              danger: true,
            ),
          ],
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _daysController,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: const InputDecoration(
            labelText: 'Faltan N días o menos',
            hintText: 'Ej: 5',
            border: OutlineInputBorder(),
            isDense: true,
          ),
          onChanged: (v) {
            final n = int.tryParse(v.trim());
            setState(() {
              _vencidos = false;
              _maxDias = n;
            });
          },
        ),
      ],
    );
  }

  Widget _dayChip(
    String label, {
    required bool selected,
    required VoidCallback onTap,
    bool danger = false,
  }) {
    final activeColor = danger ? AppTheme.danger : AppTheme.primaryColor;
    return FilterChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      selectedColor: activeColor.withValues(alpha: 0.2),
      checkmarkColor: activeColor,
      onSelected: (_) => onTap(),
    );
  }
}
