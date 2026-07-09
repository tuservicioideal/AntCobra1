import 'dart:typed_data';

import 'package:printing/printing.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:share_plus/share_plus.dart';

import '../utils/local_file_payload.dart';

class SharePrintService {
  static String? _mimeForName(String name) {
    final lower = name.toLowerCase();
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
      return 'image/jpeg';
    }
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.docx')) {
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    }
    if (lower.endsWith('.zip')) return 'application/zip';
    return null;
  }

  Future<void> sharePayload(LocalFilePayload payload) async {
    await Share.shareXFiles([
      XFile.fromData(
        payload.bytes,
        name: payload.name,
        mimeType: _mimeForName(payload.name),
      ),
    ]);
  }

  Future<void> sharePayloads(List<LocalFilePayload> payloads) async {
    if (payloads.isEmpty) return;
    await Share.shareXFiles(
      payloads
          .map(
            (p) => XFile.fromData(
              p.bytes,
              name: p.name,
              mimeType: _mimeForName(p.name),
            ),
          )
          .toList(),
    );
  }

  Future<void> printImagePayload(LocalFilePayload payload) async {
    await Printing.layoutPdf(
      onLayout: (_) async {
        final doc = pw.Document();
        final image = pw.MemoryImage(payload.bytes);
        doc.addPage(
          pw.Page(
            build: (_) => pw.Center(
              child: pw.Image(image, fit: pw.BoxFit.contain),
            ),
          ),
        );
        return doc.save();
      },
    );
  }
}
