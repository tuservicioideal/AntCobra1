import 'dart:typed_data';

import 'template_disk_cache_types.dart';

class _WebTemplateDiskCache implements TemplateDiskCache {
  final Map<int, Uint8List> _memory = {};

  @override
  Future<Uint8List?> read(int numeroCarta) async => _memory[numeroCarta];

  @override
  Future<void> write(int numeroCarta, Uint8List bytes) async {
    _memory[numeroCarta] = bytes;
  }

  @override
  Future<DateTime?> lastModified(int numeroCarta) async => null;
}

TemplateDiskCache createTemplateDiskCache() => _WebTemplateDiskCache();
