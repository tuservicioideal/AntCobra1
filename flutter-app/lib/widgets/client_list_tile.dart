import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/theme.dart';
import '../models/client_model.dart';
import '../models/semaforo.dart';
import '../services/etiqueta_catalog_service.dart';
import '../utils/client_status_ui.dart';
import 'cierre_badge.dart';
import 'tramo_filter_bar.dart';

/// List tile for a client in the dashboard.
class ClientListTile extends StatelessWidget {
  final ClientModel client;
  final VoidCallback onTap;
  final String? distanceLabel;
  final bool isCallMode;
  final bool isSelected;
  final bool showChevron;
  final bool dense;
  final Widget? trailing;
  final EtiquetaCatalogService? etiquetaCatalog;
  final int duracionDias;

  const ClientListTile({
    super.key,
    required this.client,
    required this.onTap,
    this.distanceLabel,
    this.isCallMode = false,
    this.isSelected = false,
    this.showChevron = true,
    this.dense = false,
    this.trailing,
    this.etiquetaCatalog,
    this.duracionDias = 59,
  });

  @override
  Widget build(BuildContext context) {
    final statusColor = AppTheme.getStatusColor(client.estadoGestion);

    return Card(
      margin: EdgeInsets.symmetric(
        horizontal: dense ? 8 : 16,
        vertical: dense ? 2 : 4,
      ),
      elevation: isSelected ? 2 : 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(dense ? 10 : 14),
        side: BorderSide(
          color: isSelected ? AppTheme.primaryColor : Colors.transparent,
          width: isSelected ? 2 : 0,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        mouseCursor: SystemMouseCursors.click,
        borderRadius: BorderRadius.circular(dense ? 10 : 14),
        child: Padding(
          padding: EdgeInsets.all(dense ? 8 : 12),
          child: Row(
            children: [
              // Avatar with initials
              CircleAvatar(
                radius: dense ? 16 : 22,
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
                        TramoBadge(
                          tramo: client.tramoActual,
                          dense: true,
                        ),
                        if (normalizeSemaforo(client.semaforo).isNotEmpty) ...[
                          const SizedBox(width: 6),
                          Tooltip(
                            message: labelSemaforo(client.semaforo),
                            child: Container(
                              width: 10,
                              height: 10,
                              decoration: BoxDecoration(
                                color: colorSemaforo(client.semaforo),
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: Colors.white,
                                  width: 1,
                                ),
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(width: 6),
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
                        if (client.campanaBanco.isNotEmpty) ...[
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
                        CierreBadge(
                          client: client,
                          now: DateTime.now(),
                          duracionDias: duracionDias,
                          dense: true,
                        ),
                        if (client.distrito.isNotEmpty) ...[
                          const SizedBox(width: 8),
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
                        ] else
                          const Spacer(),
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
              if (trailing != null)
                trailing!
              else if (showChevron)
                Icon(Icons.chevron_right, size: 18, color: Colors.grey.shade400),
            ],
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
      case 'no_hizo_pedido':
        return 'SIN PEDIDO';
      case 'completo_pedido_socia':
        return 'PED. SOCIA';
      case 'pendiente':
        return 'PENDIENTE';
      default:
        return estado.toUpperCase();
    }
  }
}

/// Shared column spec so header and rows stay aligned.
abstract final class ClientTableCols {
  static const clienteFlex = 4;
  static const dniFlex = 2;
  static const phoneFlex = 2;
  static const campanaWidth = 72.0;
  static const atrasoWidth = 52.0;
  static const cierreWidth = 72.0;
  static const deudaWidth = 76.0;
  static const estadoWidth = 80.0;
  static const distanciaWidth = 72.0;
}

class _ColLabel extends StatelessWidget {
  final String text;
  final TextAlign align;

  const _ColLabel(this.text, {this.align = TextAlign.start});

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      textAlign: align,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 11),
    );
  }
}

/// Header row for [ClientDataRow] tables.
class ClientTableHeader extends StatelessWidget {
  final bool isCallMode;
  final bool showCampana;
  final bool showAtraso;
  final bool showCierre;
  final bool showDistance;

  const ClientTableHeader({
    super.key,
    this.isCallMode = false,
    this.showCampana = true,
    this.showAtraso = true,
    this.showCierre = false,
    this.showDistance = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      color: Colors.grey.shade100,
      child: Row(
        children: [
          const Expanded(
            flex: ClientTableCols.clienteFlex,
            child: _ColLabel('Cliente'),
          ),
          const Expanded(
            flex: ClientTableCols.dniFlex,
            child: _ColLabel('DNI'),
          ),
          if (isCallMode)
            const Expanded(
              flex: ClientTableCols.phoneFlex,
              child: _ColLabel('Teléfono'),
            ),
          if (showCampana)
            const SizedBox(
              width: ClientTableCols.campanaWidth,
              child: _ColLabel('Campaña'),
            ),
          if (showAtraso)
            const SizedBox(
              width: ClientTableCols.atrasoWidth,
              child: _ColLabel('Atraso', align: TextAlign.end),
            ),
          if (showCierre)
            const SizedBox(
              width: ClientTableCols.cierreWidth,
              child: _ColLabel('Cierre', align: TextAlign.end),
            ),
          const SizedBox(
            width: ClientTableCols.deudaWidth,
            child: _ColLabel('Deuda', align: TextAlign.end),
          ),
          const SizedBox(width: 8),
          const SizedBox(
            width: ClientTableCols.estadoWidth,
            child: _ColLabel('Estado', align: TextAlign.end),
          ),
          if (showDistance) ...[
            const SizedBox(width: 8),
            const SizedBox(
              width: ClientTableCols.distanciaWidth,
              child: _ColLabel('Dist.', align: TextAlign.end),
            ),
          ],
        ],
      ),
    );
  }
}

/// Compact table row for wide dashboard views.
class ClientDataRow extends StatelessWidget {
  final ClientModel client;
  final VoidCallback onTap;
  final String? distanceLabel;
  final bool isCallMode;
  final bool isSelected;
  final bool showCampana;
  final bool showAtraso;
  final bool showCierre;
  final int duracionDias;
  final EtiquetaCatalogService? etiquetaCatalog;

  const ClientDataRow({
    super.key,
    required this.client,
    required this.onTap,
    this.distanceLabel,
    this.isCallMode = false,
    this.isSelected = false,
    this.showCampana = true,
    this.showAtraso = true,
    this.showCierre = false,
    this.duracionDias = 59,
    this.etiquetaCatalog,
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
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Row(
            children: [
              Expanded(
                flex: ClientTableCols.clienteFlex,
                child: Row(
                  children: [
                    TramoBadge(
                      tramo: client.tramoActual,
                      dense: true,
                    ),
                    if (normalizeSemaforo(client.semaforo).isNotEmpty) ...[
                      const SizedBox(width: 6),
                      Tooltip(
                        message: labelSemaforo(client.semaforo),
                        child: Container(
                          width: 9,
                          height: 9,
                          decoration: BoxDecoration(
                            color: colorSemaforo(client.semaforo),
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 1),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        client.displayName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        ),
                      ),
                    ),
                    if (client.isHighValue) ...[
                      const SizedBox(width: 6),
                      Text(
                        'ALTO',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.bold,
                          color: Colors.red.shade600,
                        ),
                      ),
                    ],
                    if (client.etiquetas.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      ...client.etiquetas.take(3).map((id) {
                        final color =
                            etiquetaCatalog?.findById(id)?.color ?? Colors.grey;
                        return Padding(
                          padding: const EdgeInsets.only(right: 3),
                          child: Container(
                            width: 7,
                            height: 7,
                            decoration: BoxDecoration(
                              color: color,
                              shape: BoxShape.circle,
                            ),
                          ),
                        );
                      }),
                    ],
                  ],
                ),
              ),
              Expanded(
                flex: ClientTableCols.dniFlex,
                child: Text(
                  client.numeroDocumento.isEmpty ? '—' : client.numeroDocumento,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade700,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ),
              if (isCallMode)
                Expanded(
                  flex: ClientTableCols.phoneFlex,
                  child: client.hasPhone
                      ? GestureDetector(
                          onTap: () => _dialPhone(client.telefonoMovil),
                          child: Text(
                            client.telefonoMovil,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.primaryColor,
                            ),
                          ),
                        )
                      : Text(
                          '—',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade500,
                          ),
                        ),
                ),
              if (showCampana)
                SizedBox(
                  width: ClientTableCols.campanaWidth,
                  child: Text(
                    client.campanaBanco.isEmpty ? '—' : client.campanaBanco,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                  ),
                ),
              if (showAtraso)
                SizedBox(
                  width: ClientTableCols.atrasoWidth,
                  child: Text(
                    '${client.diasAtraso}d',
                    textAlign: TextAlign.end,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: client.diasAtraso >= 60
                          ? Colors.red.shade700
                          : Colors.grey.shade700,
                    ),
                  ),
                ),
              if (showCierre)
                SizedBox(
                  width: ClientTableCols.cierreWidth,
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: CierreBadge(
                      client: client,
                      now: DateTime.now(),
                      duracionDias: duracionDias,
                      dense: true,
                    ),
                  ),
                ),
              SizedBox(
                width: ClientTableCols.deudaWidth,
                child: Text(
                  'S/ ${client.importeDeudaAsignada.toStringAsFixed(0)}',
                  textAlign: TextAlign.end,
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 12,
                    color: client.isHighValue
                        ? Colors.red.shade600
                        : Colors.grey.shade800,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: ClientTableCols.estadoWidth,
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
                  width: ClientTableCols.distanciaWidth,
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

  Future<void> _dialPhone(String phone) async {
    final normalized = phone.replaceAll(RegExp(r'[^\d+]'), '');
    final uri = Uri(scheme: 'tel', path: normalized);
    await launchUrl(uri);
  }
}
