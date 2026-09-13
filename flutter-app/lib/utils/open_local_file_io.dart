import 'package:open_filex/open_filex.dart';

import 'local_file_payload.dart';

Future<void> openLocalFile(LocalFilePayload payload) async {
  final path = payload.path;
  if (path == null || path.isEmpty) {
    throw StateError('No hay ruta local para abrir el archivo.');
  }
  final mime = payload.mimeType;
  if (mime != null && mime.isNotEmpty) {
    await OpenFilex.open(path, type: mime);
  } else {
    await OpenFilex.open(path);
  }
}
