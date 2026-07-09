import 'dart:typed_data';

import 'package:firebase_storage/firebase_storage.dart';
import '../models/client_model.dart';
import '../utils/file_output_helper.dart';
import '../utils/local_file_payload.dart';
import '../utils/open_local_file.dart';

class DocumentDownloadService {
  final FirebaseStorage _storage = FirebaseStorage.instance;
  final Map<String, LocalFilePayload> _memoryCache = {};

  Future<LocalFilePayload> downloadLetter(CartaGenerada letter) async {
    if (letter.storagePath.isEmpty) {
      throw Exception('La carta no tiene ruta de almacenamiento.');
    }

    final cacheKey = letter.storagePath;
    final cached = _memoryCache[cacheKey];
    if (cached != null) return cached;

    final fileName =
        letter.nombreArchivo.isNotEmpty ? letter.nombreArchivo : '${letter.id}.jpg';
    final bytes = await _storage.ref(letter.storagePath).getData(10 * 1024 * 1024);
    if (bytes == null) throw Exception('No se pudo descargar la carta.');

    final payload = await writeBytesToDocuments(
      bytes: Uint8List.fromList(bytes),
      filename: fileName,
      subfolder: 'cartas_cobranzas',
    );
    _memoryCache[cacheKey] = payload;
    return payload;
  }

  Future<void> openLetter(CartaGenerada letter) async {
    final payload = await downloadLetter(letter);
    await openLocalFile(payload);
  }

  Future<List<LocalFilePayload>> downloadLetters(List<CartaGenerada> letters) async {
    final files = <LocalFilePayload>[];
    for (final letter in letters) {
      try {
        files.add(await downloadLetter(letter));
      } catch (_) {
        // Continue with remaining files.
      }
    }
    return files;
  }
}
