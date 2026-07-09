import 'dart:typed_data';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';

import 'template_disk_cache.dart' show TemplateDiskCache, createTemplateDiskCache;

class LetterTemplateCacheService {
  LetterTemplateCacheService({
    FirebaseFirestore? firestore,
    FirebaseStorage? storage,
    TemplateDiskCache? diskCache,
  })  : _db = firestore ?? FirebaseFirestore.instance,
        _storage = storage ?? FirebaseStorage.instance,
        _disk = diskCache ?? createTemplateDiskCache();

  final FirebaseFirestore _db;
  final FirebaseStorage _storage;
  final TemplateDiskCache _disk;

  static const _configDoc = 'plantillas_cartas';

  Future<List<int>> getTemplateBytes(int numeroCarta, {bool forceRefresh = false}) async {
    if (numeroCarta < 1 || numeroCarta > 5) {
      throw ArgumentError('numeroCarta debe estar entre 1 y 5');
    }

    if (!forceRefresh) {
      final cached = await _disk.read(numeroCarta);
      if (cached != null && cached.isNotEmpty) {
        final remoteUpdated = await _remoteUpdatedAt(numeroCarta);
        if (remoteUpdated == null) {
          return cached;
        }
        final localModified = await _disk.lastModified(numeroCarta);
        if (localModified == null || !remoteUpdated.isAfter(localModified)) {
          return cached;
        }
      }
    }

    final storagePath = await _resolveStoragePath(numeroCarta);
    final ref = _storage.ref(storagePath);
    final bytes = await ref.getData();
    if (bytes == null || bytes.isEmpty) {
      throw StateError(
        'No se encontró la plantilla Word Carta $numeroCarta en Firebase. '
        'El administrador debe subirla desde admin-app.',
      );
    }

    await _disk.write(numeroCarta, Uint8List.fromList(bytes));
    return bytes;
  }

  Future<void> prefetchTemplates({Iterable<int> numeros = const [1, 2, 3, 4, 5]}) async {
    for (final n in numeros) {
      try {
        await getTemplateBytes(n, forceRefresh: true);
      } catch (_) {
        // Skip missing templates silently during bulk prefetch.
      }
    }
  }

  Future<DateTime?> _remoteUpdatedAt(int numeroCarta) async {
    try {
      final snap = await _db.collection('configuracion').doc(_configDoc).get();
      if (!snap.exists) return null;
      final entry = snap.data()?[numeroCarta.toString()];
      if (entry is! Map) return null;
      final ts = entry['updated_at'];
      if (ts is Timestamp) return ts.toDate();
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<String> _resolveStoragePath(int numeroCarta) async {
    try {
      final snap = await _db.collection('configuracion').doc(_configDoc).get();
      final entry = snap.data()?[numeroCarta.toString()];
      if (entry is Map && entry['storage_path'] != null) {
        return entry['storage_path'].toString();
      }
    } catch (_) {
      // Fallback to default path.
    }
    return 'plantillas_carta/carta_$numeroCarta.docx';
  }
}
