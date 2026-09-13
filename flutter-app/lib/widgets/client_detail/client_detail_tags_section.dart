import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../services/etiqueta_catalog_service.dart';

/// Etiquetas asignadas al cliente. En escritorio se eligen en la ficha.
class ClientDetailTagsSection extends StatelessWidget {
  final ClientModel client;
  final EtiquetaCatalogService catalogService;
  final bool saving;
  final ValueChanged<List<String>> onSave;

  const ClientDetailTagsSection({
    super.key,
    required this.client,
    required this.catalogService,
    required this.onSave,
    this.saving = false,
  });

  @override
  Widget build(BuildContext context) {
    final catalog = catalogService.etiquetas;
    final assigned = client.etiquetas.toSet();
    final orphanIds = assigned.where((id) => catalogService.findById(id) == null);

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
                Icon(Icons.label_outline, size: 18, color: AppTheme.primaryColor),
                const SizedBox(width: 8),
                Text(
                  'Etiquetas',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    color: Colors.grey.shade800,
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
            const SizedBox(height: 8),
            if (catalog.isEmpty)
              Text(
                'Sin etiquetas disponibles (el admin debe publicarlas).',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              )
            else
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  ...catalog.map((tag) {
                    final isOn = assigned.contains(tag.id);
                    return FilterChip(
                      label: Text(tag.nombre, style: const TextStyle(fontSize: 11)),
                      selected: isOn,
                      selectedColor: tag.color.withValues(alpha: 0.25),
                      checkmarkColor: tag.color,
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      side: BorderSide(
                        color: isOn
                            ? tag.color.withValues(alpha: 0.55)
                            : Colors.grey.shade300,
                      ),
                      onSelected: saving
                          ? null
                          : (selected) => _toggle(tag.id, selected),
                    );
                  }),
                  ...orphanIds.map(
                    (id) => Chip(
                      label: Text(id, style: const TextStyle(fontSize: 11)),
                      visualDensity: VisualDensity.compact,
                      padding: EdgeInsets.zero,
                      deleteIcon: const Icon(Icons.close, size: 14),
                      onDeleted: saving ? null : () => _toggle(id, false),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  void _toggle(String id, bool selected) {
    final next = client.etiquetas.toSet();
    if (selected) {
      next.add(id);
    } else {
      next.remove(id);
    }
    onSave(next.toList());
  }
}
