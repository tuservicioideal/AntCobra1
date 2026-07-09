import 'dart:typed_data';

abstract class TemplateDiskCache {
  Future<Uint8List?> read(int numeroCarta);
  Future<void> write(int numeroCarta, Uint8List bytes);
  Future<DateTime?> lastModified(int numeroCarta);
}
