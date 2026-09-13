import 'package:intl/intl.dart';

import '../models/client_model.dart';
import 'phone_contact_launcher.dart';

final _deudaFormat = NumberFormat('#,##0.00', 'es_PE');
final _varRe = RegExp(r'\{([a-z_]+)\}');

/// Construye el mapa de valores desde un cliente (+ nombre del gestor).
Map<String, String> buildWhatsAppPlaceholderMap({
  required ClientModel client,
  String gestorNombre = '',
}) {
  final amount = client.importeDeudaPendiente > 0
      ? client.importeDeudaPendiente
      : client.importeDeudaAsignada;
  final name = client.displayName.trim();
  return {
    'nombre': name.isNotEmpty ? name : 'estimado/a',
    'dni': _orDash(client.numeroDocumento),
    'codigo': _orDash(client.codigoCliente),
    'deuda': amount > 0 ? 'S/ ${_deudaFormat.format(amount)}' : '—',
    'dias_atraso': client.diasAtraso > 0 ? '${client.diasAtraso}' : '—',
    'tramo': client.tramoActual > 0 ? '${client.tramoActual}' : '—',
    'direccion': _orDash(client.fullAddress),
    'distrito': _orDash(client.distrito),
    'telefono': _orDash(client.telefonoMovil),
    'gestor': gestorNombre.trim().isNotEmpty ? gestorNombre.trim() : '—',
  };
}

Map<String, String> sampleWhatsAppPlaceholders() {
  return {
    'nombre': 'Juan Pérez',
    'dni': '12345678',
    'codigo': 'CLI-001',
    'deuda': 'S/ 1.234,56',
    'dias_atraso': '45',
    'tramo': '2',
    'direccion': 'Av. Ejemplo 123, Lima',
    'distrito': 'San Juan de Lurigancho',
    'telefono': '987654321',
    'gestor': 'María Gestora',
  };
}

/// Sustituye `{variable}` en [cuerpo]. Claves desconocidas quedan como `—`.
String renderWhatsAppPlantilla(
  String cuerpo, {
  required Map<String, String> values,
}) {
  if (cuerpo.trim().isEmpty) {
    return buildWhatsAppMessage(
      clientName: values['nombre'] ?? '',
    );
  }
  return cuerpo.replaceAllMapped(_varRe, (m) {
    final key = m.group(1)!;
    final v = values[key];
    if (v == null || v.isEmpty) return '—';
    return v;
  });
}

String _orDash(String raw) {
  final t = raw.trim();
  return t.isEmpty ? '—' : t;
}
