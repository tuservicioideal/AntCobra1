import 'package:flutter/material.dart';

/// Escala fija de voluntad de pago (un valor por cliente).
class SemaforoNivel {
  final String id;
  final String label;
  final Color color;

  const SemaforoNivel({
    required this.id,
    required this.label,
    required this.color,
  });
}

/// Id especial solo para filtros (no se persiste).
const String kSemaforoSinClasificar = '__sin__';

const List<SemaforoNivel> kSemaforoNiveles = [
  SemaforoNivel(id: 'rojo', label: 'Renuente', color: Color(0xFFDC2626)),
  SemaforoNivel(id: 'naranja', label: 'Resistente', color: Color(0xFFEA580C)),
  SemaforoNivel(id: 'amarillo', label: 'Indefinido', color: Color(0xFFEAB308)),
  SemaforoNivel(id: 'lima', label: 'Dispuesto', color: Color(0xFF84CC16)),
  SemaforoNivel(id: 'verde', label: 'Cooperativo', color: Color(0xFF16A34A)),
];

SemaforoNivel? findSemaforo(String? id) {
  if (id == null || id.isEmpty) return null;
  for (final n in kSemaforoNiveles) {
    if (n.id == id) return n;
  }
  return null;
}

String normalizeSemaforo(String? raw) {
  final key = (raw ?? '').trim().toLowerCase();
  return findSemaforo(key)?.id ?? '';
}

String labelSemaforo(String? id) {
  final n = findSemaforo(id);
  return n?.label ?? 'Sin clasificar';
}

Color colorSemaforo(String? id) {
  final n = findSemaforo(id);
  return n?.color ?? const Color(0xFF94A3B8);
}
