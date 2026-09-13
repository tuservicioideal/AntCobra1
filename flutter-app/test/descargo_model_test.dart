import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/models/descargo_model.dart';

void main() {
  test('labels de tipos de descargo cubren casos de campo', () {
    expect(DescargoTipos.label(DescargoTipos.noEsTitular), 'No es el titular');
    expect(
        DescargoTipos.label(DescargoTipos.noConoceTitular), 'No conoce al titular');
    expect(DescargoTipos.todos.length, 6);
  });

  test('fromMap parsea evidencias foto/audio', () {
    final m = DescargoModel.fromMap('d1', {
      'tipo_respuesta': DescargoTipos.noEsTitular,
      'texto': 'Dijo no ser la persona buscada.',
      'gestor_nombre': 'Juan',
      'fecha': '2026-09-09T10:00:00',
      'evidencias': [
        {
          'tipo': 'foto',
          'storage_path': 'a/b.jpg',
          'download_url': 'https://x/y.jpg',
          'mime_type': 'image/jpeg',
          'size_bytes': 100,
        },
        {
          'tipo': 'audio',
          'storage_path': 'a/b.m4a',
          'download_url': 'https://x/y.m4a',
          'mime_type': 'audio/m4a',
          'size_bytes': 200,
        },
      ],
    });
    expect(m.fotoCount, 1);
    expect(m.audioCount, 1);
    expect(m.fechaFormatted.contains('09/09/2026'), isTrue);
  });
}
