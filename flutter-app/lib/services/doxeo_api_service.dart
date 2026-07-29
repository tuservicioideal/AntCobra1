import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Comando de consulta Doxeo (texto que antecede al DNI en Telegram).
class DoxeoCommand {
  final String id;
  final String name;
  final String command;
  final String description;
  final String chatRef;

  const DoxeoCommand({
    required this.id,
    required this.name,
    this.command = '',
    this.description = '',
    this.chatRef = '',
  });

  factory DoxeoCommand.fromJson(Map<String, dynamic> json) {
    return DoxeoCommand(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      command: json['command']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      chatRef: json['chat_ref']?.toString() ?? '',
    );
  }

  /// Vista previa de cómo quedará el mensaje para un DNI dado.
  String previewMessage(String dni) {
    final tpl = command.trim();
    if (tpl.isEmpty) return dni;
    if (tpl.contains('{dni}')) return tpl.replaceAll('{dni}', dni).trim();
    return '$tpl $dni'.trim();
  }
}

class DoxeoReplyMedia {
  final bool isImage;
  final bool downloaded;
  final String mimeType;
  final String dataBase64;
  final String savedFile;

  const DoxeoReplyMedia({
    this.isImage = false,
    this.downloaded = false,
    this.mimeType = '',
    this.dataBase64 = '',
    this.savedFile = '',
  });

  factory DoxeoReplyMedia.fromJson(Map<String, dynamic> json) {
    return DoxeoReplyMedia(
      isImage: json['is_image'] == true,
      downloaded: json['downloaded'] == true,
      mimeType: json['mime_type']?.toString() ?? '',
      dataBase64: json['data_base64']?.toString() ?? '',
      savedFile: json['saved_file']?.toString() ?? '',
    );
  }
}

class DoxeoReply {
  final int id;
  final String date;
  final String text;
  final DoxeoReplyMedia? media;

  const DoxeoReply({
    this.id = 0,
    this.date = '',
    this.text = '',
    this.media,
  });

  factory DoxeoReply.fromJson(Map<String, dynamic> json) {
    final rawMedia = json['media'];
    return DoxeoReply(
      id: (json['id'] as num?)?.toInt() ?? 0,
      date: json['date']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
      media: rawMedia is Map<String, dynamic>
          ? DoxeoReplyMedia.fromJson(rawMedia)
          : null,
    );
  }
}

class DoxeoQueryResult {
  final String dni;
  final String status; // ok | timeout | error
  final String error;
  final String commandName;
  final String messageSent;
  final String rawReply;
  final Map<String, dynamic> parsed;
  final List<DoxeoReply> replies;

  const DoxeoQueryResult({
    this.dni = '',
    this.status = '',
    this.error = '',
    this.commandName = '',
    this.messageSent = '',
    this.rawReply = '',
    this.parsed = const {},
    this.replies = const [],
  });

  factory DoxeoQueryResult.fromJson(Map<String, dynamic> json) {
    final rawParsed = json['parsed'];
    final rawReplies = json['replies'];
    final command = json['command'];
    return DoxeoQueryResult(
      dni: json['dni']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
      error: json['error']?.toString() ?? '',
      commandName:
          command is Map<String, dynamic> ? command['name']?.toString() ?? '' : '',
      messageSent: json['message_sent']?.toString() ?? '',
      rawReply: json['raw_reply']?.toString() ?? '',
      parsed: rawParsed is Map<String, dynamic> ? rawParsed : const {},
      replies: rawReplies is List
          ? rawReplies
              .whereType<Map<String, dynamic>>()
              .map(DoxeoReply.fromJson)
              .toList()
          : const [],
    );
  }

  bool get isOk => status == 'ok';

  String get nombre => parsed['nombre']?.toString() ?? '';

  List<String> get phones => parsed['phones'] is List
      ? (parsed['phones'] as List).map((e) => e.toString()).toList()
      : const [];

  List<String> get addresses => parsed['addresses'] is List
      ? (parsed['addresses'] as List).map((e) => e.toString()).toList()
      : const [];

  List<DoxeoReply> get repliesWithImage =>
      replies.where((r) => (r.media?.dataBase64 ?? '').isNotEmpty).toList();
}

class DoxeoStatus {
  final bool sessionAuthorized;
  final String userName;
  final int commands;

  const DoxeoStatus({
    this.sessionAuthorized = false,
    this.userName = '',
    this.commands = 0,
  });

  factory DoxeoStatus.fromJson(Map<String, dynamic> json) {
    final user = json['user'];
    return DoxeoStatus(
      sessionAuthorized: json['session_authorized'] == true,
      userName: user is Map<String, dynamic>
          ? user['display_name']?.toString() ?? ''
          : '',
      commands: (json['commands'] as num?)?.toInt() ?? 0,
    );
  }
}

class DoxeoException implements Exception {
  final String message;
  final int? statusCode;

  const DoxeoException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

/// Cliente REST del backend Doxeo/Telegram (panel twi).
///
/// La URL base y la API key se guardan en SharedPreferences para que el
/// gestor las configure una sola vez en el APK.
class DoxeoApiService {
  static const _kBaseUrlKey = 'doxeo_base_url';
  static const _kApiKeyKey = 'doxeo_api_key';
  static const _defaultBaseUrl = 'http://192.168.1.100:8080';

  String _baseUrl = '';
  String _apiKey = '';

  String get baseUrl => _baseUrl;
  String get apiKey => _apiKey;
  bool get isConfigured => _baseUrl.isNotEmpty && _apiKey.isNotEmpty;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = (prefs.getString(_kBaseUrlKey) ?? '').trim();
    _apiKey = (prefs.getString(_kApiKeyKey) ?? '').trim();
  }

  Future<void> save({required String baseUrl, required String apiKey}) async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    _apiKey = apiKey.trim();
    await prefs.setString(_kBaseUrlKey, _baseUrl);
    await prefs.setString(_kApiKeyKey, _apiKey);
  }

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'X-API-Key': _apiKey,
      };

  Never _throwFor(http.Response res) {
    String detail = res.body;
    try {
      final decoded = jsonDecode(res.body);
      if (decoded is Map && decoded['detail'] != null) {
        detail = decoded['detail'].toString();
      }
    } catch (_) {}
    throw DoxeoException(
      detail.isEmpty ? 'Error ${res.statusCode}' : detail,
      statusCode: res.statusCode,
    );
  }

  Future<DoxeoStatus> getStatus() async {
    final res = await http
        .get(_uri('/api/doxeo/mobile/status'), headers: _headers)
        .timeout(const Duration(seconds: 20));
    if (res.statusCode != 200) _throwFor(res);
    return DoxeoStatus.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<List<DoxeoCommand>> listCommands() async {
    final res = await http
        .get(_uri('/api/doxeo/mobile/commands'), headers: _headers)
        .timeout(const Duration(seconds: 20));
    if (res.statusCode != 200) _throwFor(res);
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final raw = body['commands'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(DoxeoCommand.fromJson)
        .toList();
  }

  /// Lanza la consulta Telegram (comando + DNI). Puede tardar hasta ~2 min
  /// porque el backend espera la respuesta del bot/contacto.
  Future<DoxeoQueryResult> runQuery({
    required String dni,
    String? commandId,
    int timeoutSec = 60,
  }) async {
    final payload = <String, dynamic>{
      'dni': dni,
      'timeout': timeoutSec,
      if (commandId != null && commandId.isNotEmpty) 'command_id': commandId,
    };
    final res = await http
        .post(_uri('/api/doxeo/mobile/query'), headers: _headers, body: jsonEncode(payload))
        .timeout(Duration(seconds: timeoutSec + 40));
    if (res.statusCode != 200) _throwFor(res);
    return DoxeoQueryResult.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  static Future<String> suggestedBaseUrl() async => _defaultBaseUrl;
}
