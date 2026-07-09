import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';

/// Minimal GPS status chip with expandable advanced panel.
class ClientDetailGpsStrip extends StatefulWidget {
  final bool gpsLoading;
  final bool gpsReady;
  final String? gpsError;
  final ClientModel client;
  final String verifiedDateFormatted;
  final bool savingVerifiedLocation;
  final bool saving;
  final VoidCallback onRetry;
  final VoidCallback? onOpenSettings;
  final VoidCallback onSaveVerified;
  final VoidCallback onOpenVerifiedMaps;

  const ClientDetailGpsStrip({
    super.key,
    required this.gpsLoading,
    required this.gpsReady,
    this.gpsError,
    required this.client,
    required this.verifiedDateFormatted,
    required this.savingVerifiedLocation,
    required this.saving,
    required this.onRetry,
    this.onOpenSettings,
    required this.onSaveVerified,
    required this.onOpenVerifiedMaps,
  });

  @override
  State<ClientDetailGpsStrip> createState() => _ClientDetailGpsStripState();
}

class _ClientDetailGpsStripState extends State<ClientDetailGpsStrip> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
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

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(
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
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: statusColor,
                      ),
                    ),
                  ),
                  if (!widget.gpsLoading && !widget.gpsReady)
                    TextButton(
                      onPressed: widget.onRetry,
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      child: const Text('Reintentar', style: TextStyle(fontSize: 12)),
                    ),
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                    color: AppTheme.textMuted,
                  ),
                ],
              ),
            ),
          ),
          if (_expanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (widget.gpsReady)
                    Text(
                      'Coordenadas actuales del dispositivo.',
                      style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                    ),
                  if (!widget.gpsLoading && !widget.gpsReady) ...[
                    Text(
                      widget.gpsError ?? 'GPS no disponible',
                      style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                    ),
                    if (widget.onOpenSettings != null) ...[
                      const SizedBox(height: 6),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton(
                          onPressed: widget.onOpenSettings,
                          child: const Text('Abrir ajustes', style: TextStyle(fontSize: 12)),
                        ),
                      ),
                    ],
                  ],
                  if (widget.client.hasVerifiedLocation) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Verificada: ${widget.client.ubicacionVerificadaLat.toStringAsFixed(5)}, '
                      '${widget.client.ubicacionVerificadaLng.toStringAsFixed(5)}'
                      '${widget.client.ubicacionVerificadaGestor.isNotEmpty ? ' · ${widget.client.ubicacionVerificadaGestor}' : ''}'
                      '${widget.verifiedDateFormatted.isNotEmpty ? ' · ${widget.verifiedDateFormatted}' : ''}',
                      style: TextStyle(fontSize: 11, color: Colors.grey.shade800),
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: widget.onOpenVerifiedMaps,
                        icon: const Icon(Icons.map_outlined, size: 16),
                        label: const Text('Maps verificada', style: TextStyle(fontSize: 12)),
                      ),
                    ),
                  ],
                  if (widget.gpsReady) ...[
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed: (widget.savingVerifiedLocation || widget.saving)
                          ? null
                          : widget.onSaveVerified,
                      icon: widget.savingVerifiedLocation
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.add_location_alt_outlined, size: 18),
                      label: Text(
                        widget.savingVerifiedLocation
                            ? 'Guardando…'
                            : 'Guardar ubicación actual (posible domicilio)',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppTheme.primary,
                        side: BorderSide(color: AppTheme.primary.withValues(alpha: 0.4)),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
