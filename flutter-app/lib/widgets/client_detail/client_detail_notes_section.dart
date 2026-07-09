import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../utils/direcciones_conocidas.dart';
import 'detail_section_tile.dart';

class ClientDetailNotesSection extends StatefulWidget {
  final TextEditingController notesController;
  final TextEditingController contactPhoneController;
  final TextEditingController contactAddressController;
  final TextEditingController contactNoteController;
  final bool savingContact;
  final bool gpsReady;
  final String nivelConfianza;
  final ValueChanged<String>? onNivelConfianzaChanged;
  final VoidCallback? onFillAddressWithGps;
  final Future<bool> Function() onSaveContact;

  const ClientDetailNotesSection({
    super.key,
    required this.notesController,
    required this.contactPhoneController,
    required this.contactAddressController,
    required this.contactNoteController,
    required this.savingContact,
    this.gpsReady = false,
    this.nivelConfianza = nivelConfiable,
    this.onNivelConfianzaChanged,
    this.onFillAddressWithGps,
    required this.onSaveContact,
  });

  @override
  State<ClientDetailNotesSection> createState() => _ClientDetailNotesSectionState();
}

class _ClientDetailNotesSectionState extends State<ClientDetailNotesSection> {
  bool _showFieldForm = false;

  @override
  Widget build(BuildContext context) {
    return DetailSectionTile(
      title: 'Notas',
      icon: Icons.note_alt_outlined,
      initiallyExpanded: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Nota del gestor',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: widget.notesController,
            maxLines: 3,
            decoration: const InputDecoration(
              hintText: 'Observaciones (se guardan al registrar gestión)…',
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.all(10),
              isDense: true,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Observación de campo',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ),
              if (!_showFieldForm)
                TextButton(
                  onPressed: () => setState(() => _showFieldForm = true),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: const Text('Agregar', style: TextStyle(fontSize: 12)),
                ),
            ],
          ),
          if (!_showFieldForm)
            const Padding(
              padding: EdgeInsets.only(top: 4),
              child: Text(
                'Teléfono o dirección observados. Se guardan para futuras campañas (no modifican la ficha del banco).',
                style: TextStyle(fontSize: 11, color: AppTheme.textMuted),
              ),
            ),
          if (_showFieldForm) ...[
            const SizedBox(height: 8),
            TextField(
              controller: widget.contactPhoneController,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Teléfono observado (opcional)',
                hintText: 'Puede guardar solo teléfono',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                isDense: true,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: TextField(
                    controller: widget.contactAddressController,
                    decoration: const InputDecoration(
                      labelText: 'Dirección observada (opcional)',
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      isDense: true,
                    ),
                  ),
                ),
                if (widget.onFillAddressWithGps != null) ...[
                  const SizedBox(width: 8),
                  TextButton.icon(
                    onPressed: widget.gpsReady ? widget.onFillAddressWithGps : null,
                    icon: const Icon(Icons.my_location, size: 16),
                    label: const Text('GPS', style: TextStyle(fontSize: 11)),
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 8),
            if (widget.onNivelConfianzaChanged != null)
              DropdownButtonFormField<String>(
                value: widget.nivelConfianza,
                decoration: const InputDecoration(
                  labelText: 'Nivel de confianza',
                  border: OutlineInputBorder(),
                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  isDense: true,
                ),
                items: const [
                  DropdownMenuItem(value: nivelConfiable, child: Text('Confiable')),
                  DropdownMenuItem(value: nivelDudosa, child: Text('Dudosa')),
                  DropdownMenuItem(value: nivelDescartada, child: Text('Descartada')),
                ],
                onChanged: (v) {
                  if (v != null) widget.onNivelConfianzaChanged!(v);
                },
              ),
            if (widget.onNivelConfianzaChanged != null) const SizedBox(height: 8),
            TextField(
              controller: widget.contactNoteController,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Nota (obligatoria)',
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.all(10),
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: widget.savingContact
                    ? null
                    : () async {
                        final ok = await widget.onSaveContact();
                        if (mounted && ok) setState(() => _showFieldForm = false);
                      },
                icon: widget.savingContact
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.save_outlined, size: 18),
                label: Text(
                  widget.savingContact ? 'Guardando…' : 'Guardar observación',
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
