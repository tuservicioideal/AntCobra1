import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/visita_historial.dart';
import '../../utils/client_status_ui.dart';

/// Timeline de visitas/gestiones pasadas de un cliente.
class ClientDetailHistorySection extends StatelessWidget {
  final List<VisitaHistorial> visitas;
  final bool loading;
  final bool showCombinedLabel;

  const ClientDetailHistorySection({
    super.key,
    required this.visitas,
    this.loading = false,
    this.showCombinedLabel = false,
  });

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (visitas.isEmpty) return const SizedBox.shrink();

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
                Text(
                  showCombinedLabel
                      ? 'Historial de visitas (todas las cuentas)'
                      : 'Historial de visitas',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: Colors.grey.shade800,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ...visitas.take(20).map(_visitTile),
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
