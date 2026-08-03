import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';

/// Hosting manifest for the field APK (parallel to admin EXE latest.json).
const String apkUpdateManifestUrl =
    'https://clase-001.web.app/updates/apk-latest.json';

class ApkUpdateInfo {
  final String version;
  final String filename;
  final String url;
  final String sha256;
  final String notes;
  final String publishedAt;
  final String minVersion;

  const ApkUpdateInfo({
    required this.version,
    required this.filename,
    required this.url,
    required this.sha256,
    required this.notes,
    required this.publishedAt,
    required this.minVersion,
  });

  factory ApkUpdateInfo.fromJson(Map<String, dynamic> data) {
    return ApkUpdateInfo(
      version: (data['version'] ?? '').toString().trim(),
      filename: (data['filename'] ?? '').toString().trim(),
      url: (data['url'] ?? '').toString().trim(),
      sha256: (data['sha256'] ?? '').toString().trim().toLowerCase(),
      notes: (data['notes'] ?? '').toString().trim(),
      publishedAt: (data['published_at'] ?? '').toString().trim(),
      minVersion: (data['min_version'] ?? '').toString().trim(),
    );
  }

  bool isNewerThan(String currentVersion) =>
      _compareVersions(version, currentVersion) > 0;
}

class ApkDownloadResult {
  final bool success;
  final String message;
  final String? apkPath;

  const ApkDownloadResult({
    required this.success,
    required this.message,
    this.apkPath,
  });
}

typedef ApkProgressCb = void Function(String message, double fraction);

List<int> _versionTuple(String version) {
  final parts = <int>[];
  for (final chunk
      in version.trim().replaceFirst(RegExp(r'^[vV]'), '').split('.')) {
    final digits = chunk.replaceAll(RegExp(r'[^0-9]'), '');
    parts.add(int.tryParse(digits) ?? 0);
  }
  return parts.isEmpty ? const [0] : parts;
}

int _compareVersions(String a, String b) {
  final aa = _versionTuple(a);
  final bb = _versionTuple(b);
  final len = aa.length > bb.length ? aa.length : bb.length;
  for (var i = 0; i < len; i++) {
    final x = i < aa.length ? aa[i] : 0;
    final y = i < bb.length ? bb[i] : 0;
    if (x != y) return x.compareTo(y);
  }
  return 0;
}

bool get supportsApkSelfUpdate =>
    !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

class AppUpdateService {
  Future<String> currentVersion() async {
    final info = await PackageInfo.fromPlatform();
    return info.version;
  }

  Future<ApkUpdateInfo> fetchLatest({
    Duration timeout = const Duration(seconds: 20),
  }) async {
    final resp =
        await http.get(Uri.parse(apkUpdateManifestUrl)).timeout(timeout);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception('HTTP ${resp.statusCode} al consultar el manifiesto');
    }
    final decoded = jsonDecode(resp.body);
    if (decoded is! Map) {
      throw const FormatException('Manifiesto de actualización inválido');
    }
    return ApkUpdateInfo.fromJson(
      decoded.map((k, v) => MapEntry(k.toString(), v)),
    );
  }

  Future<ApkDownloadResult> downloadUpdate(
    ApkUpdateInfo info, {
    ApkProgressCb? progress,
  }) async {
    if (info.url.isEmpty) {
      return const ApkDownloadResult(
        success: false,
        message: 'El manifiesto no incluye URL de descarga.',
      );
    }

    progress?.call('Preparando descarga…', 0.02);
    final dir = await getTemporaryDirectory();
    final updatesDir = Directory('${dir.path}/apk_updates');
    if (!await updatesDir.exists()) {
      await updatesDir.create(recursive: true);
    }
    final name = info.filename.isNotEmpty
        ? info.filename
        : 'app-recaudo-legal-${info.version}.apk';
    final apkPath = '${updatesDir.path}/$name';

    try {
      progress?.call('Descargando actualización…', 0.05);
      final client = http.Client();
      try {
        final req = http.Request('GET', Uri.parse(info.url));
        final streamed =
            await client.send(req).timeout(const Duration(minutes: 5));
        if (streamed.statusCode < 200 || streamed.statusCode >= 300) {
          return ApkDownloadResult(
            success: false,
            message: 'Error HTTP ${streamed.statusCode} al descargar.',
          );
        }
        final total = streamed.contentLength ?? 0;
        final sink = File(apkPath).openWrite();
        var done = 0;
        await for (final chunk in streamed.stream) {
          sink.add(chunk);
          done += chunk.length;
          if (total > 0) {
            progress?.call(
              'Descargando… ${done ~/ (1024 * 1024)} / ${total ~/ (1024 * 1024)} MB',
              (done / total).clamp(0.05, 0.9),
            );
          }
        }
        await sink.close();
      } finally {
        client.close();
      }
    } on SocketException {
      return const ApkDownloadResult(
        success: false,
        message: 'Sin conexión a Internet.',
      );
    } catch (e) {
      return ApkDownloadResult(
        success: false,
        message: 'Error al descargar: $e',
      );
    }

    if (info.sha256.isNotEmpty) {
      progress?.call('Verificando archivo…', 0.92);
      final digest = await _sha256File(apkPath);
      if (digest != info.sha256) {
        try {
          await File(apkPath).delete();
        } catch (_) {}
        return const ApkDownloadResult(
          success: false,
          message:
              'El APK descargado no coincide con el hash esperado (corrupto).',
        );
      }
    }

    progress?.call('Listo', 1.0);
    return ApkDownloadResult(
      success: true,
      message: 'Actualización ${info.version} descargada.',
      apkPath: apkPath,
    );
  }

  Future<bool> openInstaller(String apkPath) async {
    final result = await OpenFilex.open(
      apkPath,
      type: 'application/vnd.android.package-archive',
    );
    return result.type == ResultType.done;
  }

  Future<String> _sha256File(String path) async {
    final digest = await sha256.bind(File(path).openRead()).first;
    return digest.toString();
  }
}
