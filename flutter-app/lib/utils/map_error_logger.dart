import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _prefKeyLastMapError = 'last_map_error';
const _prefKeyLastMapErrorAt = 'last_map_error_at';

/// Logs estructurados del mapa y persiste el último error para diagnóstico en campo.
class MapErrorLogger {
  static void log(String phase, Object error, [StackTrace? stack]) {
    final message = '[$phase] $error';
    debugPrint('[ClientMap] $message');
    if (stack != null) {
      debugPrint('[ClientMap] $stack');
    }
  }

  static Future<void> persistLastError(String phase, Object error) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final text = '[$phase] ${DateTime.now().toIso8601String()}: $error';
      await prefs.setString(_prefKeyLastMapError, text);
      await prefs.setInt(
        _prefKeyLastMapErrorAt,
        DateTime.now().millisecondsSinceEpoch,
      );
    } catch (e) {
      debugPrint('[ClientMap] No se pudo persistir error: $e');
    }
  }

  static Future<void> clearLastError() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_prefKeyLastMapError);
      await prefs.remove(_prefKeyLastMapErrorAt);
    } catch (_) {}
  }

  static Future<String?> readLastError() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(_prefKeyLastMapError);
    } catch (_) {
      return null;
    }
  }
}
