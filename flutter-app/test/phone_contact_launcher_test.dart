import 'package:app_recaudo_legal/utils/phone_contact_launcher.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('normalizePhoneForWhatsApp', () {
    test('formats spaced local mobile', () {
      expect(normalizePhoneForWhatsApp('987 654 321'), '51987654321');
    });

    test('formats international prefix', () {
      expect(normalizePhoneForWhatsApp('+51 987 654 321'), '51987654321');
    });

    test('keeps already normalized number', () {
      expect(normalizePhoneForWhatsApp('51987654321'), '51987654321');
    });

    test('returns null for empty input', () {
      expect(normalizePhoneForWhatsApp(''), isNull);
      expect(normalizePhoneForWhatsApp('   '), isNull);
    });

    test('returns null for invalid numbers', () {
      expect(normalizePhoneForWhatsApp('12345'), isNull);
      expect(normalizePhoneForWhatsApp('812345678'), isNull);
    });
  });

  group('buildWhatsAppMessage', () {
    test('uses client name in template', () {
      expect(
        buildWhatsAppMessage(clientName: 'Juan Pérez'),
        contains('Juan Pérez'),
      );
    });

    test('fallback when name is empty', () {
      expect(
        buildWhatsAppMessage(clientName: ''),
        contains('estimado/a'),
      );
    });
  });

  group('buildWhatsAppUri', () {
    test('builds wa.me uri with encoded message', () {
      final uri = buildWhatsAppUri(
        phone: '987654321',
        message: 'Hola Juan',
      );
      expect(uri, isNotNull);
      expect(uri!.scheme, 'https');
      expect(uri.host, 'wa.me');
      expect(uri.path, '/51987654321');
      expect(uri.queryParameters['text'], 'Hola Juan');
    });

    test('returns null for invalid phone', () {
      expect(
        buildWhatsAppUri(phone: 'invalid', message: 'Hola'),
        isNull,
      );
    });
  });
}
