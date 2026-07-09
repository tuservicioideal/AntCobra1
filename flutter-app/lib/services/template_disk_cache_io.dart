import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import 'template_disk_cache_types.dart';

class _IoTemplateDiskCache implements TemplateDiskCache {
  Future<String> _path(int numeroCarta) async {
    final dir = await getApplicationDocumentsDirectory();
    return '${dir.path}${Platform.pathSeparator}plantillas${Platform.pathSeparator}carta_$numeroCarta.docx';
  }

  @override
  Future<Uint8List?> read(int numeroCarta) async {
    final file = File(await _path(numeroCarta));
    if (!await file.exists()) return null;
    return file.readAsBytes();
  }

  @override
  Future<void> write(int numeroCarta, Uint8List bytes) async {
    final file = File(await _path(numeroCarta));
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes, flush: true);
  }

  @override
  Future<DateTime?> lastModified(int numeroCarta) async {
    final file = File(await _path(numeroCarta));
    if (!await file.exists()) return null;
    return file.lastModified();
  }
}

TemplateDiskCache createTemplateDiskCache() => _IoTemplateDiskCache();
