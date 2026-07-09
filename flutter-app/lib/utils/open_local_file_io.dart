import 'package:open_filex/open_filex.dart';

import 'local_file_payload.dart';

Future<void> openLocalFile(LocalFilePayload payload) async {
  final path = payload.path;
  if (path == null || path.isEmpty) {
    throw StateError('No hay ruta local para abrir el archivo.');
  }
  await OpenFilex.open(path);
}
