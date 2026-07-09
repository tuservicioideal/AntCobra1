import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../utils/client_display_format.dart';
import '../../utils/direcciones_conocidas.dart';
import '../../utils/phone_contact_launcher.dart';
import 'client_detail_contact_agenda_section.dart';
import 'detail_section_tile.dart';

class ClientDetailLocationSection extends StatefulWidget {
  final ClientModel client;
  final List<DireccionConocida> direcciones;
  final bool loadingDirecciones;
  final bool gpsLoading;
  final bool gpsReady;
  final String? gpsError;
  final double? currentLat;
  final double? currentLng;
  final bool savingGpsAnnotation;
  final bool saving;
  final VoidCallback? onOpenClientMaps;
  final VoidCallback? onOpenVerifiedMaps;
  final VoidCallback? onSaveGpsAnnotation;
  final VoidCallback? onRetryGps;
  final ContactEntryCallback? onUpdateContactEntry;
  final Future<void> Function(DireccionConocida entry, int deltaOrden)? onReorderContactEntry;

  const ClientDetailLocationSection({
    super.key,
    required this.client,
    required this.direcciones,
    required this.loadingDirecciones,
    this.gpsLoading = false,
    this.gpsReady = false,
    this.gpsError,
    this.currentLat,
    this.currentLng,
    this.savingGpsAnnotation = false,
    this.saving = false,
    this.onOpenClientMaps,
    this.onOpenVerifiedMaps,
    this.onSaveGpsAnnotation,
    this.onRetryGps,
    this.onUpdateContactEntry,
    this.onReorderContactEntry,
  });

  @override
  State<ClientDetailLocationSection> createState() =>
      _ClientDetailLocationSectionState();
}

class _ClientDetailLocationSectionState extends State<ClientDetailLocationSection> {
  @override
  Widget build(BuildContext context) {
    final client = widget.client;
    final addr = formatAddressDisplay(client.direccion);
    final subtitle = locationSubtitle(client.distrito, client.departamento);
    final showRef = !referenceRedundant(client.direccion, client.referencia);

    return DetailSectionTile(
      title: 'Ubicación y contacto',
      icon: Icons.location_on_outlined,
      initiallyExpanded: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (addr.isNotEmpty) ...[
            Text(
              addr,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppTheme.textPrimary,
                height: 1.35,
              ),
            ),
            if (subtitle.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  subtitle,
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
              ),
          ],
          if (showRef && client.referencia.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Ref. ${formatAddressDisplay(client.referencia)}',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (client.hasCoordinates && widget.onOpenClientMaps != null)
                OutlinedButton.icon(
                  onPressed: widget.onOpenClientMaps,
                  icon: const Icon(Icons.map_outlined, size: 16),
                  label: const Text('Abrir dirección', style: TextStyle(fontSize: 12)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primary,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  ),
                ),
              if (client.hasVerifiedLocation && widget.onOpenVerifiedMaps != null)
                OutlinedButton.icon(
                  onPressed: widget.onOpenVerifiedMaps,
                  icon: const Icon(Icons.verified_outlined, size: 16),
                  label: const Text('Maps verificada', style: TextStyle(fontSize: 12)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primary,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  ),
                ),
            ],
          ),
          _buildGpsAnnotationBlock(),
          if (client.telefonoMovil.isNotEmpty || client.correo.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 10),
            if (client.telefonoMovil.isNotEmpty)
              _contactRow(
                icon: Icons.phone_outlined,
                label: client.telefonoMovil,
                onTap: () => launchUrl(
                  Uri.parse('tel:${client.telefonoMovil}'),
                  mode: LaunchMode.externalApplication,
                ),
              ),
            if (client.telefonoMovil.isNotEmpty)
              _contactRow(
                icon: Icons.chat_outlined,
                label: 'WhatsApp · ${client.telefonoMovil}',
                onTap: () => _openWhatsApp(context, client),
              ),
            if (client.correo.isNotEmpty)
              _contactRow(
                icon: Icons.email_outlined,
                label: client.correo,
                onTap: () => launchUrl(
                  Uri.parse('mailto:${client.correo}'),
                  mode: LaunchMode.externalApplication,
                ),
              ),
          ],
          if (widget.loadingDirecciones ||
              widget.direcciones.any((d) => d.fuente != 'Registro banco (principal)')) ...[
            const SizedBox(height: 12),
            ClientDetailContactAgendaSection(
              direcciones: widget.direcciones,
              loading: widget.loadingDirecciones,
              onUpdateEntry: widget.onUpdateContactEntry,
              onReorderEntry: widget.onReorderContactEntry,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildGpsAnnotationBlock() {
    final statusColor = widget.gpsLoading
        ? AppTheme.info
        : widget.gpsReady
            ? AppTheme.success
            : AppTheme.danger;
    final statusLabel = widget.gpsLoading
        ? 'Obteniendo GPS…'
        : widget.gpsReady
            ? 'GPS listo'
            : 'Sin señal GPS';

    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.primary.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.primary.withValues(alpha: 0.15)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(
                  widget.gpsLoading
                      ? Icons.gps_not_fixed
                      : widget.gpsReady
                          ? Icons.gps_fixed
                          : Icons.gps_off,
                  size: 18,
                  color: statusColor,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    statusLabel,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: statusColor,
                    ),
                  ),
                ),
                if (!widget.gpsLoading && !widget.gpsReady && widget.onRetryGps != null)
                  TextButton(
                    onPressed: widget.onRetryGps,
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: const Text('Reintentar', style: TextStyle(fontSize: 12)),
                  ),
              ],
            ),
            if (widget.gpsReady &&
                widget.currentLat != null &&
                widget.currentLng != null) ...[
              const SizedBox(height: 6),
              Text(
                'Coordenadas actuales: '
                '${widget.currentLat!.toStringAsFixed(5)}, ${widget.currentLng!.toStringAsFixed(5)}',
                style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
              ),
            ],
            if (!widget.gpsLoading && !widget.gpsReady && widget.gpsError != null) ...[
              const SizedBox(height: 6),
              Text(
                widget.gpsError!,
                style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
              ),
            ],
            const SizedBox(height: 8),
            Text(
              'Si el domicilio del banco no coincide, anote aquí la ubicación donde está el cliente. '
              'No modifica la ficha del banco; queda en direcciones conocidas.',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600, height: 1.35),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: (widget.gpsReady &&
                        !widget.savingGpsAnnotation &&
                        !widget.saving &&
                        widget.onSaveGpsAnnotation != null)
                    ? widget.onSaveGpsAnnotation
                    : null,
                icon: widget.savingGpsAnnotation
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.add_location_alt_outlined, size: 18),
                label: Text(
                  widget.savingGpsAnnotation
                      ? 'Guardando…'
                      : 'Guardar ubicación actual (posible domicilio)',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                ),
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openWhatsApp(BuildContext context, ClientModel client) async {
    final launched = await launchWhatsApp(
      phone: client.telefonoMovil,
      clientName: client.displayName,
    );
    if (!context.mounted || launched) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('No se pudo abrir WhatsApp. Verifique que esté instalado.'),
      ),
    );
  }

  Widget _contactRow({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            children: [
              Icon(icon, size: 18, color: AppTheme.textSecondary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.primary,
                  ),
                ),
              ),
              const Icon(Icons.chevron_right, size: 18, color: AppTheme.textMuted),
            ],
          ),
        ),
      ),
    );
  }
}
