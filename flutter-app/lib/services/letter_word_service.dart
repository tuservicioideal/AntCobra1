import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';

import '../models/client_model.dart';
import '../utils/file_output_helper.dart';
import '../utils/local_file_payload.dart';
import 'letter_placeholders.dart';
import 'letter_template_cache_service.dart';

/// Result of bulk combined Word generation for a gestor.
class WordCombinedResult {
  const WordCombinedResult({
    this.payload,
    this.letterCount = 0,
    this.failedCount = 0,
    this.mixedTemplates = false,
  });

  final LocalFilePayload? payload;
  final int letterCount;
  final int failedCount;
  final bool mixedTemplates;
}

class _FilledClientDoc {
  const _FilledClientDoc({
    required this.bytes,
    required this.cartaId,
    required this.placeholders,
  });

  final List<int> bytes;
  final int cartaId;
  final LetterPlaceholders placeholders;
}

class LetterWordService {
  LetterWordService({LetterTemplateCacheService? cacheService})
      : _cache = cacheService ?? LetterTemplateCacheService();

  final LetterTemplateCacheService _cache;

  static const _documentXmlPath = 'word/document.xml';
  static const _pageBreakParagraph =
      '<w:p><w:r><w:br w:type="page"/></w:r></w:p>';

  static final _wpBlockRe = RegExp(r'(<w:p\b.*?</w:p>)', dotAll: true);
  static final _wtRe = RegExp(r'(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)', dotAll: true);
  static final _wrBlockRe = RegExp(r'(<w:r\b.*?</w:r>)', dotAll: true);
  static final _wpOpenRe = RegExp(r'(<w:p\b[^>]*>)');
  static final _wpPprRe = RegExp(r'(<w:pPr\b.*?</w:pPr>)', dotAll: true);
  static final _wrPrRe = RegExp(r'(<w:rPr\b.*?</w:rPr>)', dotAll: true);
  static final _unfilledTagRe = RegExp(r'\{\{[A-Z_]+\}\}');
  static final _bodyOpenRe = RegExp(r'<w:body[^>]*>');
  static final _sectPrRe = RegExp(r'<w:sectPr\b.*?</w:sectPr>', dotAll: true);

  static bool shouldProcessZipMember(String name) {
    if (!name.startsWith('word/') || !name.endsWith('.xml')) return false;
    if (name.contains('/_rels/')) return false;
    final base = name.split('/').last;
    if (base.startsWith('settings') ||
        base.startsWith('styles') ||
        base.startsWith('theme')) {
      return false;
    }
    return true;
  }

  static bool paragraphNeedsTagProcessing(
    String combined,
    Map<String, String> mapping,
  ) {
    if (_unfilledTagRe.hasMatch(combined)) return true;
    if (combined.contains('{{') || combined.contains('}}')) return true;
    return mapping.keys.any((tag) => combined.contains(tag));
  }

  static String escapeXml(String value) {
    return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
  }

  static String extractBodyContent(String documentXml) {
    final bodyOpen = _bodyOpenRe.firstMatch(documentXml);
    if (bodyOpen == null) {
      throw StateError('Documento Word inválido: falta w:body.');
    }
    final bodyStart = bodyOpen.end;
    final sectPr = _sectPrRe.firstMatch(documentXml);
    final bodyEnd = sectPr != null
        ? sectPr.start
        : documentXml.indexOf('</w:body>', bodyStart);
    if (bodyEnd < 0) {
      throw StateError('Documento Word inválido: falta cierre de w:body.');
    }
    return documentXml.substring(bodyStart, bodyEnd);
  }

  static String readDocumentXml(List<int> docxBytes) {
    final decoded = ZipDecoder().decodeBytes(docxBytes);
    for (final file in decoded.files) {
      if (file.isFile && file.name == _documentXmlPath) {
        return utf8.decode(
          Uint8List.fromList(file.content as List<int>),
          allowMalformed: true,
        );
      }
    }
    throw StateError('Documento Word inválido: falta word/document.xml.');
  }

  static List<int> mergeFilledDocxBytes(List<List<int>> docs) {
    if (docs.isEmpty) {
      throw StateError('No hay documentos para fusionar.');
    }
    if (docs.length == 1) return List<int>.from(docs.first);

    final baseArchive = ZipDecoder().decodeBytes(docs.first);
    final baseDocXml = readDocumentXml(docs.first);
    final sectPrMatch = _sectPrRe.firstMatch(baseDocXml);
    final insertAt = sectPrMatch?.start ??
        baseDocXml.lastIndexOf('</w:body>');
    if (insertAt < 0) {
      throw StateError('Documento Word inválido: no se pudo insertar contenido.');
    }

    final suffix = sectPrMatch != null
        ? baseDocXml.substring(insertAt)
        : '</w:body></w:document>';

    final buffer = StringBuffer(baseDocXml.substring(0, insertAt));
    for (var i = 1; i < docs.length; i++) {
      buffer.write(_pageBreakParagraph);
      buffer.write(extractBodyContent(readDocumentXml(docs[i])));
    }
    buffer.write(suffix);

    final mergedBytes = utf8.encode(buffer.toString());
    final encoded = Archive();
    for (final file in baseArchive.files) {
      if (!file.isFile) continue;
      final bytes = file.name == _documentXmlPath
          ? mergedBytes
          : Uint8List.fromList(file.content as List<int>);
      encoded.addFile(ArchiveFile(file.name, bytes.length, bytes));
    }

    final out = ZipEncoder().encode(encoded);
    if (out.isEmpty) {
      throw StateError('No se pudo empaquetar el documento Word fusionado.');
    }
    return out;
  }

  static String resolveSeccionLabel(ClientModel client) {
    final key = client.seccionKey.trim();
    if (key.contains('_')) return key.split('_').last;
    if (client.seccion.trim().isNotEmpty) return client.seccion.trim();
    return key.isNotEmpty ? key : 'SIN_SECCION';
  }

  Future<LocalFilePayload> generateWordForClient({
    required ClientModel client,
    int? templateId,
    String gestorName = '',
    String gestorPhone = '',
    String campaignName = '',
  }) async {
    final filled = await _fillForClient(
      client: client,
      templateId: templateId,
      gestorName: gestorName,
      gestorPhone: gestorPhone,
      campaignName: campaignName,
    );

    final clientId =
        client.codigoCliente.isNotEmpty ? client.codigoCliente : client.id;
    final safeName = sanitizeName(
      filled.placeholders.nombre.isNotEmpty
          ? filled.placeholders.nombre
          : clientId,
    );
    final filename =
        'Carta_${filled.cartaId}_Cli${sanitizeName(clientId)}_$safeName.docx';

    return writeBytesToDocuments(
      bytes: Uint8List.fromList(filled.bytes),
      filename: filename,
      subfolder: 'cartas_word',
    );
  }

  Future<WordCombinedResult> generateWordCombined({
    required List<ClientModel> clients,
    String gestorName = '',
    String gestorPhone = '',
    String campaignName = '',
    void Function(int current, int total)? onProgress,
  }) async {
    final filledDocs = <List<int>>[];
    final templateIds = <int>{};
    var failedCount = 0;

    for (var i = 0; i < clients.length; i++) {
      onProgress?.call(i + 1, clients.length);
      try {
        final filled = await _fillForClient(
          client: clients[i],
          gestorName: gestorName,
          gestorPhone: gestorPhone,
          campaignName: campaignName,
        );
        filledDocs.add(filled.bytes);
        templateIds.add(filled.cartaId);
      } catch (_) {
        failedCount++;
      }
    }

    if (filledDocs.isEmpty) {
      return WordCombinedResult(failedCount: failedCount);
    }

    final mergedBytes = mergeFilledDocxBytes(filledDocs);
    final secLabel = sanitizeName(resolveSeccionLabel(clients.first));
    final safeGestor = sanitizeName(
      gestorName.trim().isNotEmpty ? gestorName.trim() : 'Gestor',
    );
    final filename =
        'Cartas_Cobranza_Seccion_${secLabel}_$safeGestor.docx';

    final payload = await writeBytesToDocuments(
      bytes: Uint8List.fromList(mergedBytes),
      filename: filename,
      subfolder: 'cartas_word',
    );

    return WordCombinedResult(
      payload: payload,
      letterCount: filledDocs.length,
      failedCount: failedCount,
      mixedTemplates: templateIds.length > 1,
    );
  }

  Future<List<LocalFilePayload>> generateWordBulk({
    required List<ClientModel> clients,
    String gestorName = '',
    String gestorPhone = '',
    String campaignName = '',
    void Function(int current, int total)? onProgress,
  }) async {
    final files = <LocalFilePayload>[];
    for (var i = 0; i < clients.length; i++) {
      onProgress?.call(i + 1, clients.length);
      try {
        final payload = await generateWordForClient(
          client: clients[i],
          gestorName: gestorName,
          gestorPhone: gestorPhone,
          campaignName: campaignName,
        );
        files.add(payload);
      } catch (_) {
        // Continue with remaining clients.
      }
    }
    return files;
  }

  Future<LocalFilePayload?> createZipFromPayloads(List<LocalFilePayload> payloads) async {
    if (payloads.isEmpty) return null;
    final archive = Archive();
    for (final payload in payloads) {
      archive.addFile(
        ArchiveFile(payload.name, payload.bytes.length, payload.bytes),
      );
    }
    final zipBytes = ZipEncoder().encode(archive);
    if (zipBytes.isEmpty) return null;
    return writeBytesToDocuments(
      bytes: Uint8List.fromList(zipBytes),
      filename: 'cartas_word_${DateTime.now().millisecondsSinceEpoch}.zip',
      subfolder: 'cartas_word',
    );
  }

  Future<_FilledClientDoc> _fillForClient({
    required ClientModel client,
    int? templateId,
    String gestorName = '',
    String gestorPhone = '',
    String campaignName = '',
  }) async {
    final cartaId = resolveTemplateId(client, numeroCarta: templateId);
    final placeholders = mapClientToPlaceholders(
      client: client,
      gestorName: gestorName,
      gestorPhone: gestorPhone,
      campaignName: campaignName,
    );
    final missing = validatePlaceholders(placeholders);
    if (missing.isNotEmpty) {
      throw StateError('Faltan datos del cliente: ${missing.join(', ')}');
    }

    final templateBytes = await _cache.getTemplateBytes(cartaId);
    final mapping = placeholdersToTagMap(placeholders);
    final filledBytes = fillWordTemplateBytes(templateBytes, mapping);

    final unfilled = findUnfilledTagsInDocxBytes(filledBytes);
    if (unfilled.isNotEmpty) {
      throw StateError(
        'La plantilla conserva etiquetas sin reemplazar: ${unfilled.join(', ')}',
      );
    }

    return _FilledClientDoc(
      bytes: filledBytes,
      cartaId: cartaId,
      placeholders: placeholders,
    );
  }

  static List<int> fillWordTemplateBytes(
    List<int> templateBytes,
    Map<String, String> mapping,
  ) {
    final decoded = ZipDecoder().decodeBytes(templateBytes);
    final encoded = Archive();

    for (final file in decoded.files) {
      if (!file.isFile) continue;
      List<int> bytes;
      if (shouldProcessZipMember(file.name)) {
        final raw = Uint8List.fromList(file.content as List<int>);
        var xmlText = utf8.decode(raw, allowMalformed: true);
        xmlText = _replaceTagsInXml(xmlText, mapping);
        bytes = utf8.encode(xmlText);
      } else {
        bytes = Uint8List.fromList(file.content as List<int>);
      }
      encoded.addFile(ArchiveFile(file.name, bytes.length, bytes));
    }

    final out = ZipEncoder().encode(encoded);
    if (out.isEmpty) {
      throw StateError('No se pudo empaquetar el documento Word.');
    }
    return out;
  }

  static String _replaceTagsInXml(String xmlText, Map<String, String> mapping) {
    var result = xmlText;
    for (final entry in mapping.entries) {
      result = result.replaceAll(entry.key, entry.value);
    }
    result = result.replaceAllMapped(_wpBlockRe, (match) {
      final block = match.group(1)!;
      final wtMatches = _wtRe.allMatches(block).toList();
      if (wtMatches.isEmpty) return block;
      final combined = wtMatches.map((m) => m.group(2) ?? '').join();
      if (!paragraphNeedsTagProcessing(combined, mapping)) return block;
      return _replaceSplitTagsInWpBlock(block, mapping);
    });
    return result;
  }

  static String _replaceSplitTagsInWpBlock(
    String block,
    Map<String, String> mapping,
  ) {
    final wtMatches = _wtRe.allMatches(block).toList();
    if (wtMatches.isEmpty) return block;

    final combined = wtMatches.map((m) => m.group(2) ?? '').join();
    if (!paragraphNeedsTagProcessing(combined, mapping)) return block;

    var replaced = combined;
    for (final entry in mapping.entries) {
      replaced = replaced.replaceAll(entry.key, entry.value);
    }
    if (replaced == combined) return block;

    final escaped = escapeXml(replaced);
    final preserve = replaced.startsWith(' ') ||
        replaced.endsWith(' ') ||
        replaced.contains('  ') ||
        replaced.contains('\t');
    final tAttr = preserve ? ' xml:space="preserve"' : '';

    final openMatch = _wpOpenRe.firstMatch(block);
    if (openMatch == null) return block;
    final pOpen = openMatch.group(1)!;

    final pprMatch = _wpPprRe.firstMatch(block);
    final ppr = pprMatch?.group(1) ?? '';

    final wrMatches = _wrBlockRe.allMatches(block).toList();
    if (wrMatches.isEmpty) return block;
    final firstWr = wrMatches.first.group(1)!;
    final rprMatch = _wrPrRe.firstMatch(firstWr);
    final rpr = rprMatch?.group(1) ?? '';

    final newRun = '<w:r>$rpr<w:t$tAttr>$escaped</w:t></w:r>';
    return '$pOpen$ppr$newRun</w:p>';
  }
}
