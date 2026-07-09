import 'package:flutter/material.dart';

import '../services/letter_jpg_templates.dart';

/// Off-screen A4-like canvas for letter JPG capture (matches PWA proportions).
class LetterJpgCanvas extends StatelessWidget {
  final int templateId;
  final LetterJpgPlaceholders placeholders;

  const LetterJpgCanvas({
    super.key,
    required this.templateId,
    required this.placeholders,
  });

  static const double canvasWidth = 620;
  static const double canvasHeight = 877;

  @override
  Widget build(BuildContext context) {
    final title = titleByTemplate[templateId] ?? titleByTemplate[1]!;
    final bodyLines = bodyLinesForTemplate(templateId, placeholders);
    final p = placeholders;

    return Material(
      color: Colors.white,
      child: SizedBox(
        width: canvasWidth,
        height: canvasHeight,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(36, 36, 36, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFFD00000),
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  decoration: TextDecoration.underline,
                  height: 1.1,
                ),
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  'Lima, ${p.fecha}',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              _p('Señor(a): ${p.nombre}    DNI: ${p.dni}'),
              _p('Dirección: ${p.direccion}'),
              _p(
                'Código: ${p.codigo}   Zona: ${p.zona}   Sección: ${p.seccion}   Campaña: ${p.campana}',
              ),
              const SizedBox(height: 8),
              ...bodyLines.map((line) {
                final isPay = line.startsWith('CODIGO DE PAGO');
                final isUrgent = line.contains('Plazo maximo');
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    line,
                    textAlign: isPay ? TextAlign.center : TextAlign.left,
                    style: TextStyle(
                      fontSize: isPay ? 14 : 12,
                      fontWeight: isPay ? FontWeight.w700 : FontWeight.w400,
                      color: isUrgent ? const Color(0xFFD10000) : const Color(0xFF111111),
                      height: 1.3,
                    ),
                  ),
                );
              }),
              const SizedBox(height: 12),
              _p('Atentamente,'),
              _p('RECAUDO LEGAL & ABOGADOS', bold: true),
              _p('WhatsApp: 942 470 641'),
              _p('Email: recaudolegal@yahoo.com'),
              _p('Encargado: ${p.gestorNombre}   Celular: ${p.gestorCelular}', bold: true),
              const Spacer(),
              const Text(
                'Nota: Si usted ya realizo el pago, sirvase omitir este comunicado.',
                style: TextStyle(fontSize: 9, color: Color(0xFF64748B), height: 1.3),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _p(String text, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 12,
          fontWeight: bold ? FontWeight.w700 : FontWeight.w400,
          color: const Color(0xFF111111),
          height: 1.3,
        ),
      ),
    );
  }
}
