import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../models/user_model.dart';
import '../utils/section_utils.dart';

/// Opción de destino: gestor + sección Firestore.
class DestinationOption {
  final UserModel? gestor;
  final String sectionKey;
  final String label;

  const DestinationOption({
    required this.sectionKey,
    required this.label,
    this.gestor,
  });
}

/// Construye opciones de destino a partir de gestores activos y secciones libres.
List<DestinationOption> buildDestinationOptions({
  required List<UserModel> gestores,
  required List<String> destinationSections,
  bool includeUnassignedSections = true,
}) {
  final options = <DestinationOption>[];
  final assignedSections = <String>{};

  for (final gestor in gestores) {
    final keys = resolveGestorSectionKeys(gestor);
    if (gestor.isCallGestor && keys.isEmpty && gestor.uid.isNotEmpty) {
      keys.add(callSectionKeyForUid(gestor.uid));
    }
    for (final key in keys) {
      if (key.isEmpty || isReservedReassignmentSection(key)) continue;
      assignedSections.add(key);
      options.add(DestinationOption(
        gestor: gestor,
        sectionKey: key,
        label: gestorDestinationLabel(gestor, key),
      ));
    }
  }

  if (includeUnassignedSections) {
    for (final key in destinationSections) {
      if (key.isEmpty ||
          isReservedReassignmentSection(key) ||
          assignedSections.contains(key)) {
        continue;
      }
      options.add(DestinationOption(
        sectionKey: key,
        label: sectionDisplayLabel(key),
      ));
    }
  }

  options.sort((a, b) => a.label.compareTo(b.label));
  return options;
}

/// Dropdown para elegir gestor/sección destino de reasignación.
class DestinationGestorPicker extends StatelessWidget {
  const DestinationGestorPicker({
    super.key,
    required this.options,
    required this.selectedSectionKey,
    required this.onChanged,
    this.label = 'Destino',
    this.enabled = true,
  });

  final List<DestinationOption> options;
  final String? selectedSectionKey;
  final ValueChanged<String?> onChanged;
  final String label;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    if (options.isEmpty) {
      return Text(
        'No hay secciones destino disponibles',
        style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
      );
    }

    final validValue = options.any((o) => o.sectionKey == selectedSectionKey)
        ? selectedSectionKey
        : options.first.sectionKey;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        const SizedBox(height: 6),
        DropdownButtonFormField<String>(
          value: validValue,
          isExpanded: true,
          decoration: InputDecoration(
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          ),
          items: options
              .map(
                (o) => DropdownMenuItem(
                  value: o.sectionKey,
                  child: Text(o.label, style: const TextStyle(fontSize: 13)),
                ),
              )
              .toList(),
          onChanged: enabled ? onChanged : null,
        ),
      ],
    );
  }
}

/// Diálogo modal para elegir destino (gestor o sección).
Future<String?> showDestinationPickerDialog({
  required BuildContext context,
  required List<DestinationOption> options,
  String? initialSectionKey,
  String title = 'Seleccionar destino',
}) async {
  if (options.isEmpty) return null;
  var selected = initialSectionKey;
  if (selected == null || !options.any((o) => o.sectionKey == selected)) {
    selected = options.first.sectionKey;
  }

  return showDialog<String>(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setState) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(title),
        content: SizedBox(
          width: 340,
          child: DestinationGestorPicker(
            options: options,
            selectedSectionKey: selected,
            onChanged: (v) => setState(() => selected = v),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryColor,
            ),
            onPressed: () => Navigator.pop(ctx, selected),
            child: const Text('Confirmar', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    ),
  );
}
