import 'package:url_launcher/url_launcher.dart';

const _defaultWhatsAppMessageTemplate =
    'Hola {nombre}, le escribo desde App Recaudo Legal respecto a su cuenta. ¿Podemos coordinar?';

/// Strips formatting and normalizes Peruvian mobile numbers for wa.me (E.164 without +).
String? normalizePhoneForWhatsApp(
  String raw, {
  String countryCode = '51',
}) {
  var digits = raw.replaceAll(RegExp(r'[^\d]'), '');
  if (digits.isEmpty) return null;

  if (digits.startsWith(countryCode)) {
    final local = digits.substring(countryCode.length);
    if (local.length == 9 && local.startsWith('9')) return digits;
    return null;
  }

  if (digits.length == 9 && digits.startsWith('9')) {
    return '$countryCode$digits';
  }

  return null;
}

String buildWhatsAppMessage({required String clientName}) {
  final name = clientName.trim().isNotEmpty ? clientName.trim() : 'estimado/a';
  return _defaultWhatsAppMessageTemplate.replaceAll('{nombre}', name);
}

Uri? buildWhatsAppUri({
  required String phone,
  required String message,
  String countryCode = '51',
}) {
  final normalized = normalizePhoneForWhatsApp(phone, countryCode: countryCode);
  if (normalized == null) return null;

  return Uri.https('wa.me', '/$normalized', {'text': message});
}

Future<bool> launchWhatsApp({
  required String phone,
  required String clientName,
  String countryCode = '51',
}) async {
  final uri = buildWhatsAppUri(
    phone: phone,
    message: buildWhatsAppMessage(clientName: clientName),
    countryCode: countryCode,
  );
  if (uri == null) return false;

  return launchUrl(uri, mode: LaunchMode.externalApplication);
}
