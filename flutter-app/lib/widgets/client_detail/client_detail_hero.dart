import 'package:flutter/material.dart';
import '../../config/theme.dart';
import '../../models/client_model.dart';
import '../../utils/client_display_format.dart';
import '../../utils/client_status_ui.dart';

/// Compact header: identity, metrics chips, debt bar.
class ClientDetailHero extends StatelessWidget {
  final ClientModel client;

  const ClientDetailHero({super.key, required this.client});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 22,
                backgroundColor: AppTheme.primaryLight,
                child: Text(
                  client.initials,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.primary,
                    fontSize: 15,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      client.displayName,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                        color: AppTheme.textPrimary,
                        height: 1.25,
                      ),
                    ),
                    if (client.numeroDocumento.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          'DNI ${client.numeroDocumento}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              ClientStatusChip(estado: client.estadoGestion),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              _metricChip(client.cicloLabel),
              if (client.gestionEspecial)
                _metricChip('Gestión especial', color: AppTheme.warning),
              _metricChip('${client.diasAtraso} días atraso'),
              if (client.codigoCliente.isNotEmpty)
                _metricChip(client.codigoCliente),
              if (client.montoPromesaPago > 0 ||
                  client.fechaPromesaPago.trim().isNotEmpty)
                _compromisoChip(client),
            ],
          ),
          const SizedBox(height: 10),
          _DebtBar(client: client),
        ],
      ),
    );
  }

  Widget _metricChip(String label, {Color? color}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color != null
            ? color.withValues(alpha: 0.15)
            : AppTheme.divider,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: color ?? AppTheme.textSecondary,
        ),
      ),
    );
  }

  Widget _compromisoChip(ClientModel client) {
    final parts = <String>[];
    if (client.montoPromesaPago > 0) {
      parts.add('S/ ${client.montoPromesaPago.toStringAsFixed(2)}');
    }
    if (client.fechaPromesaPago.trim().isNotEmpty) {
      parts.add(client.fechaPromesaPago.trim());
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.primaryLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.25)),
      ),
      child: Text(
        'Compromiso: ${parts.join(' · ')}',
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: AppTheme.primary,
        ),
      ),
    );
  }
}

class _DebtBar extends StatelessWidget {
  final ClientModel client;

  const _DebtBar({required this.client});

  @override
  Widget build(BuildContext context) {
    final high = client.isHighValue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: high
              ? [AppTheme.danger, const Color(0xFFEF4444)]
              : [AppTheme.primary, AppTheme.accent],
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: _debtCell(
              'Asignada',
              'S/ ${client.importeDeudaAsignada.toStringAsFixed(2)}',
            ),
          ),
          Container(
            width: 1,
            height: 28,
            color: Colors.white.withValues(alpha: 0.35),
          ),
          Expanded(
            child: _debtCell(
              'Pendiente',
              'S/ ${client.importeDeudaPendiente.toStringAsFixed(2)}',
            ),
          ),
        ],
      ),
    );
  }

  Widget _debtCell(String label, String value) {
    return Column(
      children: [
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.85),
            fontSize: 10,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 15,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }
}

/// AppBar title helper exported for screen use.
String heroAppBarTitle(ClientModel client) =>
    shortClientTitle(client.displayName, client.codigoCliente);
