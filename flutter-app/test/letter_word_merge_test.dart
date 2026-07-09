import 'dart:convert';
import 'dart:typed_data';

import 'package:app_recaudo_legal/services/letter_word_service.dart';
import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';

String _minimalDocumentXml(String bodyInner) {
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
      '<w:body>$bodyInner'
      '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
      '</w:body></w:document>';
}

String _paragraph(String text) {
  return '<w:p><w:r><w:t>$text</w:t></w:r></w:p>';
}

List<int> _buildMiniDocx(String bodyInner) {
  final archive = Archive()
    ..addFile(ArchiveFile('[Content_Types].xml', 7, utf8.encode('<Types/>')))
    ..addFile(
      ArchiveFile(
        'word/document.xml',
        0,
        utf8.encode(_minimalDocumentXml(bodyInner)),
      ),
    );

  for (final file in archive.files) {
    final content = file.content as List<int>;
    file.size = content.length;
  }

  final encoded = ZipEncoder().encode(archive);
  expect(encoded, isNotEmpty);
  return encoded;
}

void main() {
  group('LetterWordService.mergeFilledDocxBytes', () {
    test('returns single doc unchanged', () {
      final doc = _buildMiniDocx(_paragraph('Carta A'));
      final merged = LetterWordService.mergeFilledDocxBytes([doc]);
      expect(merged, doc);
    });

    test('merges two documents with page break between bodies', () {
      final doc1 = _buildMiniDocx(_paragraph('Carta cliente 1'));
      final doc2 = _buildMiniDocx(_paragraph('Carta cliente 2'));

      final merged = LetterWordService.mergeFilledDocxBytes([doc1, doc2]);
      final xml = LetterWordService.readDocumentXml(merged);

      expect(xml, contains('Carta cliente 1'));
      expect(xml, contains('Carta cliente 2'));
      expect(xml, contains('<w:br w:type="page"/>'));
      expect(
        RegExp(r'Carta cliente 1').allMatches(xml).length,
        1,
      );
      expect(
        RegExp(r'Carta cliente 2').allMatches(xml).length,
        1,
      );
    });

    test('extractBodyContent excludes sectPr', () {
      final xml = _minimalDocumentXml(_paragraph('Solo cuerpo'));
      final body = LetterWordService.extractBodyContent(xml);
      expect(body, contains('Solo cuerpo'));
      expect(body, isNot(contains('sectPr')));
    });

    test('merged output is a valid zip archive', () {
      final doc1 = _buildMiniDocx(_paragraph('Uno'));
      final doc2 = _buildMiniDocx(_paragraph('Dos'));
      final merged = LetterWordService.mergeFilledDocxBytes([doc1, doc2]);

      final decoded = ZipDecoder().decodeBytes(Uint8List.fromList(merged));
      final names = decoded.files.where((f) => f.isFile).map((f) => f.name).toList();
      expect(names, contains('word/document.xml'));
    });
  });
}
