import 'package:flutter/material.dart';

typedef WordAction = void Function(String action);

class ClientDetailWordSection extends StatelessWidget {
  final bool generating;
  final int selectedTemplate;
  final ValueChanged<int> onTemplateChanged;
  final VoidCallback onGenerate;
  final WordAction? onWordAction;
  final String? lastGeneratedPath;

  const ClientDetailWordSection({
    super.key,
    required this.generating,
    required this.selectedTemplate,
    required this.onTemplateChanged,
    required this.onGenerate,
    this.onWordAction,
    this.lastGeneratedPath,
  });

  static const _templateLabels = {
    1: 'Carta 1 — Invitación',
    2: 'Carta 2 — No pierdas ser empresaria',
    3: 'Carta 3 — Requerimiento',
    4: 'Carta 4 — Insistencia',
    5: 'Carta 5 — Pre-judicial',
  };

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(Icons.description_outlined,
                    size: 20, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                const Text(
                  'Cartas Word',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Genera un documento Word personalizado en este dispositivo '
              '(no se sube a Firebase).',
              style: TextStyle(fontSize: 12, color: Colors.black54),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<int>(
              value: selectedTemplate,
              decoration: const InputDecoration(
                labelText: 'Plantilla',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              items: _templateLabels.entries
                  .map(
                    (e) => DropdownMenuItem(
                      value: e.key,
                      child: Text(e.value, style: const TextStyle(fontSize: 13)),
                    ),
                  )
                  .toList(),
              onChanged: generating ? null : (v) {
                if (v != null) onTemplateChanged(v);
              },
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: generating ? null : onGenerate,
              icon: generating
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.file_download_outlined, size: 18),
              label: Text(generating ? 'Generando Word…' : 'Generar carta Word'),
            ),
            if (lastGeneratedPath != null && lastGeneratedPath!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                lastGeneratedPath!.split(RegExp(r'[/\\]')).last,
                style: const TextStyle(fontSize: 11, color: Colors.black54),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              Row(
                children: [
                  TextButton.icon(
                    onPressed: onWordAction == null
                        ? null
                        : () => onWordAction!('abrir'),
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: const Text('Abrir'),
                  ),
                  TextButton.icon(
                    onPressed: onWordAction == null
                        ? null
                        : () => onWordAction!('compartir'),
                    icon: const Icon(Icons.share_outlined, size: 16),
                    label: const Text('Compartir'),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
