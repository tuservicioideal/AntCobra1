import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/visita_historial.dart';
import '../../utils/client_status_ui.dart';

/// Timeline de visitas/gestiones pasadas de un cliente.
class ClientDetailHistorySection extends StatefulWidget {
  final List<VisitaHistorial> visitas;
  final bool loading;
  final bool showCombinedLabel;
  final int initialCount;

  const ClientDetailHistorySection({
    super.key,
    required this.visitas,
    this.loading = false,
    this.showCombinedLabel = false,
    this.initialCount = 5,
  });

  @override
  State<ClientDetailHistorySection> createState() =>
      _ClientDetailHistorySectionState();
}

class _ClientDetailHistorySectionState
    extends State<ClientDetailHistorySection> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    if (widget.loading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (widget.visitas.isEmpty) return const SizedBox.shrink();

    final visible = _expanded
        ? widget.visitas.take(20).toList()
        : widget.visitas.take(widget.initialCount).toList();
    final hasMore = widget.visitas.length > widget.initialCount;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.history, size: 18, color: AppTheme.primaryColor),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    widget.showCombinedLabel
                        ? 'Historial (${widget.visitas.length})'
                        : 'Historial (${widget.visitas.length})',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: Colors.grey.shade800,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (widget.showCombinedLabel)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      'todas las cuentas',
                      style: TextStyle(
                          fontSize: 10, color: Colors.grey.shade600),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            ...visible.map(_visitTile),
            if (hasMore)
              TextButton.icon(
                onPressed: () => setState(() => _expanded = !_expanded),
                icon: Icon(
                  _expanded ? Icons.expand_less : Icons.expand_more,
                  size: 18,
                ),
                label: Text(
                  _expanded
                      ? 'Ver menos'
                      : 'Ver ${widget.visitas.length - widget.initialCount} más',
                  style: const TextStyle(fontSize: 12),
                ),
                style: TextButton.styleFrom(
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(0, 32),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _visitTile(VisitaHistorial v) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 8,
            height: 8,
            margin: const EdgeInsets.only(top: 5),
            decoration: BoxDecoration(
              color: AppTheme.getStatusColor(v.estadoGestion),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      v.fechaFormatted,
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade600,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      clientStatusLabel(v.estadoGestion),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.getStatusColor(v.estadoGestion),
                      ),
                    ),
                  ],
                ),
                if (v.gestorNombre.isNotEmpty)
                  Text(
                    v.gestorNombre,
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                  ),
                if (v.nivel1.isNotEmpty)
                  Text(
                    v.nivel1,
                    style: const TextStyle(fontSize: 11),
                  ),
                if (v.notaGestor.isNotEmpty)
                  Text(
                    v.notaGestor,
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade800,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
