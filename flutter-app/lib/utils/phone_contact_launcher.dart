import 'package:url_launcher/url_launcher.dart';

const defaultWhatsAppMessageTemplate =
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

/// Construye el mensaje. Si [cuerpo] es null/vacío usa el template por defecto.
String buildWhatsAppMessage({
  required String clientName,
  String? cuerpo,
  Map<String, String>? values,
}) {
  final name = clientName.trim().isNotEmpty ? clientName.trim() : 'estimado/a';
  final template =
      (cuerpo != null && cuerpo.trim().isNotEmpty)
          ? cuerpo
          : defaultWhatsAppMessageTemplate;
  if (values != null && values.isNotEmpty) {
    final merged = Map<String, String>.from(values);
    merged.putIfAbsent('nombre', () => name);
    return template.replaceAllMapped(RegExp(r'\{([a-z_]+)\}'), (m) {
      final key = m.group(1)!;
      final v = merged[key];
      if (v == null || v.isEmpty) {
        return key == 'nombre' ? name : '—';
      }
      return v;
    });
  }
  return template.replaceAll('{nombre}', name);
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
  String? message,
}) async {
  final text = message ?? buildWhatsAppMessage(clientName: clientName);
  final uri = buildWhatsAppUri(
    phone: phone,
    message: text,
    countryCode: countryCode,
  );
  if (uri == null) return false;

  return launchUrl(uri, mode: LaunchMode.externalApplication);
}
