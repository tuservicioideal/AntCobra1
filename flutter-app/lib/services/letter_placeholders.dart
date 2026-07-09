import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:intl/intl.dart';

import '../models/client_model.dart';

class LetterPlaceholders {
  final String nombre;
  final String dni;
  final String direccion;
  final String codigo;
  final String zona;
  final String seccion;
  final String campana;
  final String deuda;
  final String codigoPago;
  final String fecha;
  final String fechaVencimiento;
  final String gestorNombre;
  final String gestorCelular;

  const LetterPlaceholders({
    required this.nombre,
    required this.dni,
    required this.direccion,
    required this.codigo,
    required this.zona,
    required this.seccion,
    required this.campana,
    required this.deuda,
    required this.codigoPago,
    required this.fecha,
    required this.fechaVencimiento,
    required this.gestorNombre,
    required this.gestorCelular,
  });
}

typedef LetterJpgPlaceholders = LetterPlaceholders;

const _requiredKeys = [
  'NOMBRE',
  'DNI',
  'DIRECCION',
  'CODIGO',
  'ZONA',
  'SECCION',
  'CAMPANA',
  'DEUDA',
  'CODIGO_PAGO',
  'FECHA',
  'FECHA_VENCIMIENTO',
];

const titleByTemplate = {
  1: 'INVITACION A REINGRESO',
  2: 'NO PIERDAS SER EMPRESARIA',
  3: 'REQUERIMIENTO DE PAGO',
  4: 'INSISTENCIA DE PAGO - REQUERIMIENTO URGENTE',
  5: 'EXIGIMOS PAGO - ETAPA PRE-JUDICIAL',
};

final _unfilledTagRe = RegExp(r'\{\{[A-Z_]+\}\}');
final _tagFragmentRe = RegExp(r'\{\{[A-Z_]*|\}\}|[A-Z_]+\}\}');

int resolveTemplateId(ClientModel client, {int? numeroCarta}) {
  if (numeroCarta != null && numeroCarta >= 1 && numeroCarta <= 5) {
    return numeroCarta;
  }
  final tramo = client.tramoActual;
  if (tramo <= 1) return 1;
  if (tramo == 2) return 3;
  if (tramo >= 3) return 5;
  return 1;
}

String resolveClientZona(ClientModel client) {
  final parts = client.seccionKey.split('_');
  if (parts.length >= 2 && parts[1].isNotEmpty) {
    return parts[1];
  }
  return client.seccion;
}

LetterPlaceholders mapClientToPlaceholders({
  required ClientModel client,
  String gestorName = '',
  String gestorPhone = '',
  String campaignName = '',
}) {
  final amount = client.importeDeudaPendiente > 0
      ? client.importeDeudaPendiente
      : client.importeDeudaAsignada;
  final fecha = DateFormat('dd/MM/yyyy').format(DateTime.now());
  final deuda = NumberFormat('#,##0.00', 'es_PE').format(amount);
  final fechaVencimiento = client.fechaPromesaPago.isNotEmpty
      ? client.fechaPromesaPago
      : '—';

  return LetterPlaceholders(
    nombre: client.displayName,
    dni: client.numeroDocumento,
    direccion: client.fullAddress,
    codigo: client.codigoCliente,
    zona: resolveClientZona(client),
    seccion: client.seccionKey.isNotEmpty ? client.seccionKey : client.seccion,
    campana: campaignName.isNotEmpty ? campaignName : 'Cartera activa',
    deuda: deuda,
    codigoPago: client.codigoCliente,
    fecha: fecha,
    fechaVencimiento: fechaVencimiento,
    gestorNombre: gestorName.isNotEmpty ? gestorName : 'Gestor asignado',
    gestorCelular: gestorPhone.isNotEmpty ? gestorPhone : 'No consignado',
  );
}

Map<String, String> placeholdersToTagMap(LetterPlaceholders p) {
  return {
    '{{NOMBRE}}': p.nombre,
    '{{DNI}}': p.dni,
    '{{DIRECCION}}': p.direccion,
    '{{CODIGO}}': p.codigo,
    '{{ZONA}}': p.zona,
    '{{SECCION}}': p.seccion,
    '{{CAMPANA}}': p.campana,
    '{{DEUDA}}': p.deuda,
    '{{CODIGO_PAGO}}': p.codigoPago,
    '{{FECHA}}': p.fecha,
    '{{FECHA_VENCIMIENTO}}': p.fechaVencimiento,
    '{{GESTOR_NOMBRE}}': p.gestorNombre,
    '{{GESTOR_CELULAR}}': p.gestorCelular,
  };
}

List<String> validatePlaceholders(LetterPlaceholders p) {
  final map = {
    'NOMBRE': p.nombre,
    'DNI': p.dni,
    'DIRECCION': p.direccion,
    'CODIGO': p.codigo,
    'ZONA': p.zona,
    'SECCION': p.seccion,
    'CAMPANA': p.campana,
    'DEUDA': p.deuda,
    'CODIGO_PAGO': p.codigoPago,
    'FECHA': p.fecha,
    'FECHA_VENCIMIENTO': p.fechaVencimiento,
  };
  return _requiredKeys.where((k) => map[k]?.trim().isEmpty ?? true).toList();
}

bool _shouldProcessZipMember(String name) {
  if (!name.startsWith('word/') || !name.endsWith('.xml')) return false;
  if (name.contains('/_rels/')) return false;
  final base = name.split('/').last;
  if (base.startsWith('settings') ||
      base.startsWith('styles') ||
      base.startsWith('theme')) {
    return false;
  }
  return true;
}

List<String> _collectIssuesFromText(String text) {
  final found = <String>{};
  final fragments = <String>{};
  found.addAll(_unfilledTagRe.allMatches(text).map((m) => m.group(0)!));
  if (text.contains('{{') || text.contains('}}')) {
    for (final match in _tagFragmentRe.allMatches(text)) {
      final fragment = match.group(0)!;
      if (!found.any((tag) => tag.contains(fragment) || fragment.contains(tag))) {
        fragments.add(fragment);
      }
    }
  }
  final issues = found.toList()..sort();
  for (final fragment in fragments) {
    issues.add('[fragmento:$fragment]');
  }
  return issues;
}

List<String> findUnfilledTagsInDocxBytes(List<int> docxBytes) {
  final issues = <String>{};
  final decoded = ZipDecoder().decodeBytes(docxBytes);
  for (final file in decoded.files) {
    if (!file.isFile || !_shouldProcessZipMember(file.name)) {
      continue;
    }
    final xmlText = utf8.decode(
      Uint8List.fromList(file.content as List<int>),
      allowMalformed: true,
    );
    issues.addAll(_collectIssuesFromText(xmlText));
  }
  return issues.toList()..sort();
}

String sanitizeName(String value) {
  final cleaned = value
      .replaceAll(RegExp(r'[^\w\-]', unicode: true), '_')
      .replaceAll(RegExp(r'_+'), '_');
  return cleaned.length > 80 ? cleaned.substring(0, 80) : cleaned;
}
