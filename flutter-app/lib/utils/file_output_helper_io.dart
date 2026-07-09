import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import 'local_file_payload.dart';

Future<LocalFilePayload> writeBytesToDocuments({
  required Uint8List bytes,
  required String filename,
  required String subfolder,
}) async {
  final base = await getApplicationDocumentsDirectory();
  final dir = Directory('${base.path}${Platform.pathSeparator}$subfolder');
  if (!await dir.exists()) {
    await dir.create(recursive: true);
  }
  final file = File('${dir.path}${Platform.pathSeparator}$filename');
  await file.writeAsBytes(bytes, flush: true);
  return LocalFilePayload(bytes: bytes, name: filename, path: file.path);
}
