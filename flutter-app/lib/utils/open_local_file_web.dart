import 'local_file_payload.dart';
import '../services/share_print_service.dart';

/// En web no hay visor nativo; compartir/descargar vía el navegador.
Future<void> openLocalFile(LocalFilePayload payload) async {
  await SharePrintService().sharePayload(payload);
}
