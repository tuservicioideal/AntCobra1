import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../models/semaforo.dart';

/// Semáforo de voluntad de pago: un toque guarda el valor.
class ClientDetailSemaforoSection extends StatelessWidget {
  final ClientModel client;
  final bool saving;
  final ValueChanged<String> onSave;

  const ClientDetailSemaforoSection({
    super.key,
    required this.client,
    required this.onSave,
    this.saving = false,
  });

  @override
  Widget build(BuildContext context) {
    final current = normalizeSemaforo(client.semaforo);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.traffic, size: 18, color: AppTheme.primaryColor),
                const SizedBox(width: 8),
                Text(
                  'Semáforo',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: Colors.grey.shade800,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    labelSemaforo(current),
                    style: TextStyle(
                      fontSize: 12,
                      color: colorSemaforo(current),
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (saving) ...[
                  const SizedBox(width: 8),
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                ...kSemaforoNiveles.map((n) {
                  final selected = current == n.id;
                  return Tooltip(
                    message: n.label,
                    child: InkWell(
                      onTap: saving ? null : () => onSave(n.id),
                      borderRadius: BorderRadius.circular(20),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: selected ? 36 : 28,
                        height: selected ? 36 : 28,
                        decoration: BoxDecoration(
                          color: n.color,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: selected
                                ? Colors.black.withValues(alpha: 0.55)
                                : Colors.white,
                            width: selected ? 3 : 2,
                          ),
                          boxShadow: selected
                              ? [
                                  BoxShadow(
                                    color: n.color.withValues(alpha: 0.45),
                                    blurRadius: 6,
                                    offset: const Offset(0, 2),
                                  ),
                                ]
                              : null,
                        ),
                      ),
                    ),
                  );
                }),
                TextButton(
                  onPressed: saving || current.isEmpty
                      ? null
                      : () => onSave(''),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: const Text('Quitar', style: TextStyle(fontSize: 12)),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Rojo = renuente · Verde = cooperativo',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }
}
