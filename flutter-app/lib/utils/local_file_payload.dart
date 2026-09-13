import 'dart:typed_data';

/// Archivo en memoria; [path] solo en plataformas con sistema de archivos nativo.
class LocalFilePayload {
  const LocalFilePayload({
    required this.bytes,
    required this.name,
    this.path,
    this.mimeType,
  });

  final Uint8List bytes;
  final String name;
  final String? path;
  final String? mimeType;
}
