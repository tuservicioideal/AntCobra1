import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../services/etiqueta_catalog_service.dart';

/// Etiquetas asignadas al cliente con editor tipo bottom sheet.
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
    final assigned = client.etiquetas;

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
                const Spacer(),
                TextButton.icon(
                  onPressed: saving || catalog.isEmpty
                      ? null
                      : () => _openPicker(context),
                  icon: saving
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.edit_outlined, size: 16),
                  label: const Text('Editar'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (assigned.isEmpty)
              Text(
                catalog.isEmpty
                    ? 'Sin etiquetas disponibles (el admin debe publicarlas).'
                    : 'Sin etiquetas asignadas.',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              )
            else
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: assigned.map((id) {
                  final def = catalogService.findById(id);
                  final color = def?.color ?? Colors.grey;
                  final name = def?.nombre ?? id;
                  return Chip(
                    label: Text(name, style: const TextStyle(fontSize: 11)),
                    backgroundColor: color.withValues(alpha: 0.15),
                    side: BorderSide(color: color.withValues(alpha: 0.4)),
                    padding: EdgeInsets.zero,
                    visualDensity: VisualDensity.compact,
                  );
                }).toList(),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _openPicker(BuildContext context) async {
    final selected = Set<String>.from(client.etiquetas);
    final catalog = catalogService.etiquetas;

    final result = await showModalBottomSheet<Set<String>>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Etiquetas del cliente',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: Colors.grey.shade800,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: catalog.map((tag) {
                      final isOn = selected.contains(tag.id);
                      return FilterChip(
                        label: Text(tag.nombre),
                        selected: isOn,
                        selectedColor: tag.color.withValues(alpha: 0.25),
                        checkmarkColor: tag.color,
                        onSelected: (v) {
                          setModalState(() {
                            if (v) {
                              selected.add(tag.id);
                            } else {
                              selected.remove(tag.id);
                            }
                          });
                        },
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: () => Navigator.pop(ctx, selected),
                    child: const Text('Guardar etiquetas'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    if (result != null) {
      onSave(result.toList());
    }
  }
}
