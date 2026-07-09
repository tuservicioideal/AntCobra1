import 'package:flutter/material.dart';
import '../config/theme.dart';

String clientStatusLabel(String estado) {
  switch (estado) {
    case 'visitado_habido':
      return 'Visitado Habido';
    case 'visitado_no_habido':
      return 'No Habido';
    case 'fallecido_inubicable':
      return 'Fallecido/Inubicable';
    case 'suplantacion':
      return 'Suplantación';
    case 'pago_no_registrado':
      return 'Pago No Registrado';
    case 'devolucion_pendiente':
      return 'Devolución pendiente';
    case 'pendiente':
      return 'Pendiente';
    default:
      return estado;
  }
}

class ClientStatusChip extends StatelessWidget {
  final String estado;

  const ClientStatusChip({super.key, required this.estado});

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.getStatusColor(estado);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        clientStatusLabel(estado),
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
