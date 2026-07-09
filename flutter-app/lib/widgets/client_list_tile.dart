import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/theme.dart';
import '../models/client_model.dart';
import '../services/etiqueta_catalog_service.dart';
import '../utils/client_status_ui.dart';

/// List tile for a client in the dashboard.
class ClientListTile extends StatelessWidget {
  final ClientModel client;
  final VoidCallback onTap;
  final String? distanceLabel;
  final bool isCallMode;
  final bool showCampanaBadge;
  final bool isSelected;
  final bool showChevron;
  final EtiquetaCatalogService? etiquetaCatalog;

  const ClientListTile({
    super.key,
    required this.client,
    required this.onTap,
    this.distanceLabel,
    this.isCallMode = false,
    this.showCampanaBadge = false,
    this.isSelected = false,
    this.showChevron = true,
    this.etiquetaCatalog,
  });

  @override
  Widget build(BuildContext context) {
    final statusColor = AppTheme.getStatusColor(client.estadoGestion);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      elevation: isSelected ? 2 : 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: isSelected ? AppTheme.primaryColor : Colors.transparent,
          width: isSelected ? 2 : 0,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        mouseCursor: SystemMouseCursors.click,
        borderRadius: BorderRadius.circular(14),        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Avatar with initials
              CircleAvatar(
                radius: 22,
                backgroundColor: statusColor.withValues(alpha: 0.12),
                child: Text(
                  client.initials,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: statusColor,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(width: 12),

              // Client info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            client.displayName,
                            style: const TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 14,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (client.isHighValue)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 5,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.red.shade50,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.trending_up,
                                    size: 10, color: Colors.red.shade600),
                                const SizedBox(width: 2),
                                Text(
                                  'ALTO',
                                  style: TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.red.shade600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        Text(
                          'DNI: ${client.numeroDocumento}',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey.shade600,
                          ),
                        ),
                        if (showCampanaBadge && client.campanaBanco.isNotEmpty) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 5,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.blue.shade50,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              client.campanaBanco,
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.w600,
                                color: Colors.blue.shade700,
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(width: 8),
                        if (client.distrito.isNotEmpty)
                          Expanded(
                            child: Text(
                              client.distrito,
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.grey.shade500,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                    ),
                    if (isCallMode && client.hasPhone) ...[
                      const SizedBox(height: 3),
                      GestureDetector(
                        onTap: () => _dialPhone(client.telefonoMovil),
                        child: Row(
                          children: [
                            Icon(
                              Icons.phone,
                              size: 12,
                              color: AppTheme.primaryColor,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              client.telefonoMovil,
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppTheme.primaryColor,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (client.cuentasMismoDni > 1) ...[
                      const SizedBox(height: 3),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.indigo.shade50,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '+${client.cuentasMismoDni - 1} cuenta${client.cuentasMismoDni - 1 == 1 ? '' : 's'}',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: Colors.indigo.shade700,
                          ),
                        ),
                      ),
                    ],
                    if (client.etiquetas.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 4,
                        runSpacing: 2,
                        children: client.etiquetas.take(3).map((id) {
                          final def = etiquetaCatalog?.findById(id);
                          final color = def?.color ?? Colors.grey;
                          return Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: color,
                              shape: BoxShape.circle,
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                    if (isCallMode && client.hasPromesa) ...[
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Icon(
                            Icons.event_available,
                            size: 12,
                            color: Colors.green.shade600,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            client.montoPromesaPago > 0
                                ? 'Promesa S/ ${client.montoPromesaPago.toStringAsFixed(0)}'
                                : 'Con promesa',
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.green.shade700,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ],
                    if (distanceLabel != null) ...[
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Icon(
                            Icons.near_me_outlined,
                            size: 12,
                            color: Colors.grey.shade500,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            distanceLabel!,
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              color: AppTheme.primaryColor.withValues(alpha: 0.85),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(width: 8),

              // Debt + Status
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    'S/ ${client.importeDeudaAsignada.toStringAsFixed(0)}',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                      color: client.isHighValue
                          ? Colors.red.shade600
                          : Colors.grey.shade800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      _shortStatus(client.estadoGestion),
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 9,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(width: 4),
              if (showChevron)
                Icon(Icons.chevron_right, size: 18, color: Colors.grey.shade400),            ],
          ),
        ),
      ),
    );
  }

  Future<void> _dialPhone(String phone) async {
    final normalized = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri(scheme: 'tel', path: normalized);
    await launchUrl(uri);
  }

  String _shortStatus(String estado) {
    switch (estado) {
      case 'visitado_habido':
        return 'HABIDO';
      case 'visitado_no_habido':
        return 'NO HABIDO';
      case 'fallecido_inubicable':
        return 'FALLECIDO';
      case 'suplantacion':
        return 'SUPLANT.';
      case 'pago_no_registrado':
        return 'PAGO N/R';
      case 'pendiente':
        return 'PENDIENTE';
      default:
        return estado.toUpperCase();
    }
  }
}

/// Compact table row for wide dashboard views.
class ClientDataRow extends StatelessWidget {
  final ClientModel client;
  final VoidCallback onTap;
  final String? distanceLabel;
  final bool isCallMode;
  final bool isSelected;

  const ClientDataRow({
    super.key,
    required this.client,
    required this.onTap,
    this.distanceLabel,
    this.isCallMode = false,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    final statusColor = AppTheme.getStatusColor(client.estadoGestion);
    return Material(
      color: isSelected
          ? AppTheme.primaryColor.withValues(alpha: 0.08)
          : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        mouseCursor: SystemMouseCursors.click,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Expanded(
                flex: 3,
                child: Text(
                  client.displayName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                ),
              ),
              Expanded(
                flex: 2,
                child: Text(
                  isCallMode && client.hasPhone
                      ? client.telefonoMovil
                      : client.numeroDocumento,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                ),
              ),
              Expanded(
                child: Text(
                  'S/ ${client.importeDeudaAsignada.toStringAsFixed(0)}',
                  textAlign: TextAlign.end,
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 88,
                child: Text(
                  clientStatusLabel(client.estadoGestion),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.end,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: statusColor,
                  ),
                ),
              ),
              if (distanceLabel != null) ...[
                const SizedBox(width: 8),
                SizedBox(
                  width: 72,
                  child: Text(
                    distanceLabel!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.end,
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}