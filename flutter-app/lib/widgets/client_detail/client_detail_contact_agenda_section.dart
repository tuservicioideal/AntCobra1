import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../utils/client_display_format.dart';
import '../../utils/direcciones_conocidas.dart';

typedef ContactEntryCallback = Future<void> Function(
  DireccionConocida entry, {
  String? nivelConfianza,
  int? orden,
  bool? oculto,
  bool? esPrincipal,
});

/// Lista editable de direcciones/teléfonos conocidos (credibilidad y orden).
class ClientDetailContactAgendaSection extends StatefulWidget {
  final List<DireccionConocida> direcciones;
  final bool loading;
  final ContactEntryCallback? onUpdateEntry;
  final Future<void> Function(DireccionConocida entry, int deltaOrden)? onReorderEntry;

  const ClientDetailContactAgendaSection({
    super.key,
    required this.direcciones,
    this.loading = false,
    this.onUpdateEntry,
    this.onReorderEntry,
  });

  @override
  State<ClientDetailContactAgendaSection> createState() =>
      _ClientDetailContactAgendaSectionState();
}

class _ClientDetailContactAgendaSectionState
    extends State<ClientDetailContactAgendaSection> {
  bool _showAll = false;
  bool _showDescartadas = false;

  List<DireccionConocida> get _activas => widget.direcciones
      .where((d) => d.fuente != 'Registro banco (principal)' && !d.oculto)
      .toList();

  List<DireccionConocida> get _descartadas => widget.direcciones
      .where((d) => d.fuente != 'Registro banco (principal)' && d.oculto)
      .toList();

  List<DireccionConocida> _visibleActivas() {
    final list = _activas;
    if (_showAll || list.length <= 3) return list;
    return list.take(3).toList();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.loading) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(8),
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }

    if (_activas.isEmpty && _descartadas.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: AppTheme.info.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppTheme.info.withValues(alpha: 0.2)),
          ),
          child: const Text(
            'Estos datos se guardan en la oficina y reaparecen si el cliente vuelve en otra campaña.',
            style: TextStyle(fontSize: 11, color: AppTheme.textSecondary, height: 1.35),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Otras direcciones y teléfonos',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: Colors.grey.shade600,
            letterSpacing: 0.3,
          ),
        ),
        const SizedBox(height: 6),
        ..._visibleActivas().map(_entryTile),
        if (_activas.length > 3 && !_showAll)
          TextButton(
            onPressed: () => setState(() => _showAll = true),
            child: Text(
              'Ver todas (${_activas.length})',
              style: const TextStyle(fontSize: 12),
            ),
          ),
        if (_descartadas.isNotEmpty) ...[
          const SizedBox(height: 8),
          InkWell(
            onTap: () => setState(() => _showDescartadas = !_showDescartadas),
            child: Row(
              children: [
                Icon(
                  _showDescartadas ? Icons.expand_less : Icons.expand_more,
                  size: 18,
                  color: Colors.grey.shade600,
                ),
                const SizedBox(width: 4),
                Text(
                  'Descartadas (${_descartadas.length})',
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                ),
              ],
            ),
          ),
          if (_showDescartadas) ...[
            const SizedBox(height: 4),
            ..._descartadas.map(_entryTile),
          ],
        ],
      ],
    );
  }

  Widget _entryTile(DireccionConocida d) {
    final editable = d.isEditable && widget.onUpdateEntry != null;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: d.esPrincipal
                ? AppTheme.primary.withValues(alpha: 0.4)
                : AppTheme.border,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: _entryBody(d)),
                if (editable) _entryActions(d),
              ],
            ),
            if (editable) ...[
              const SizedBox(height: 8),
              _nivelSelector(d),
            ],
          ],
        ),
      ),
    );
  }

  Widget _entryBody(DireccionConocida d) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (d.esPrincipal)
          const Padding(
            padding: EdgeInsets.only(bottom: 4),
            child: Text(
              'Principal',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: AppTheme.primary,
              ),
            ),
          ),
        if (d.isPhoneOnly)
          Text(
            'Tel: ${d.telefono ?? ''}',
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          )
        else if (d.direccion.isNotEmpty)
          Text(
            formatAddressDisplay(d.direccion),
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
          ),
        if (!d.isPhoneOnly && d.telefono != null && d.telefono!.isNotEmpty)
          Text(
            'Tel: ${d.telefono}',
            style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
          ),
        Text(
          d.fuente,
          style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
        ),
        Text(
          nivelConfianzaLabel(d.nivelConfianza),
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            color: _nivelColor(d.nivelConfianza),
          ),
        ),
      ],
    );
  }

  Color _nivelColor(String nivel) {
    switch (nivel) {
      case nivelConfiable:
        return AppTheme.success;
      case nivelDudosa:
        return AppTheme.warning;
      case nivelDescartada:
        return AppTheme.danger;
      default:
        return AppTheme.textSecondary;
    }
  }

  Widget _nivelSelector(DireccionConocida d) {
    return Wrap(
      spacing: 6,
      children: [
        for (final nivel in [nivelConfiable, nivelDudosa, nivelDescartada])
          ChoiceChip(
            label: Text(
              nivelConfianzaLabel(nivel),
              style: const TextStyle(fontSize: 10),
            ),
            selected: d.nivelConfianza == nivel,
            onSelected: (_) => widget.onUpdateEntry?.call(
              d,
              nivelConfianza: nivel,
              oculto: nivel == nivelDescartada ? true : false,
            ),
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
          ),
      ],
    );
  }

  Widget _entryActions(DireccionConocida d) {
    return Column(
      children: [
        IconButton(
          tooltip: 'Marcar principal',
          icon: Icon(
            d.esPrincipal ? Icons.star : Icons.star_border,
            size: 20,
            color: d.esPrincipal ? AppTheme.warning : AppTheme.textMuted,
          ),
          onPressed: () => widget.onUpdateEntry?.call(d, esPrincipal: !d.esPrincipal),
          visualDensity: VisualDensity.compact,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
        ),
        if (widget.onReorderEntry != null) ...[
          IconButton(
            tooltip: 'Subir',
            icon: const Icon(Icons.arrow_upward, size: 18),
            onPressed: () => widget.onReorderEntry?.call(d, -1),
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
          ),
          IconButton(
            tooltip: 'Bajar',
            icon: const Icon(Icons.arrow_downward, size: 18),
            onPressed: () => widget.onReorderEntry?.call(d, 1),
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
          ),
        ],
        IconButton(
          tooltip: d.oculto ? 'Restaurar' : 'Descartar',
          icon: Icon(
            d.oculto ? Icons.restore : Icons.visibility_off_outlined,
            size: 18,
            color: AppTheme.danger,
          ),
          onPressed: () => widget.onUpdateEntry?.call(d, oculto: !d.oculto),
          visualDensity: VisualDensity.compact,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
        ),
      ],
    );
  }
}
