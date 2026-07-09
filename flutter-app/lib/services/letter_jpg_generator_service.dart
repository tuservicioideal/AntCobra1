import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:image/image.dart' as img;

import '../widgets/letter_jpg_canvas.dart';
import 'letter_jpg_templates.dart';

class LetterJpgGeneratorService {
  Future<Uint8List> generateJpegBytes({
    required BuildContext context,
    required int templateId,
    required LetterJpgPlaceholders placeholders,
    double pixelRatio = 2.0,
  }) async {
    final key = GlobalKey();
    final overlay = OverlayEntry(
      builder: (ctx) => Positioned(
        left: -20000,
        top: 0,
        child: RepaintBoundary(
          key: key,
          child: LetterJpgCanvas(
            templateId: templateId,
            placeholders: placeholders,
          ),
        ),
      ),
    );

    final overlayState = Overlay.of(context, rootOverlay: true);
    overlayState.insert(overlay);

    try {
      await Future<void>.delayed(const Duration(milliseconds: 80));
      await WidgetsBinding.instance.endOfFrame;

      final boundary = key.currentContext?.findRenderObject() as RenderRepaintBoundary?;
      if (boundary == null) {
        throw StateError('No se pudo renderizar la carta.');
      }

      final uiImage = await boundary.toImage(pixelRatio: pixelRatio);
      final byteData = await uiImage.toByteData(format: ui.ImageByteFormat.png);
      if (byteData == null) {
        throw StateError('No se pudo capturar la imagen de la carta.');
      }

      final pngBytes = byteData.buffer.asUint8List();
      final decoded = img.decodeImage(pngBytes);
      if (decoded == null) {
        throw StateError('No se pudo codificar la carta JPG.');
      }
      return Uint8List.fromList(img.encodeJpg(decoded, quality: 96));
    } finally {
      overlay.remove();
    }
  }
}
