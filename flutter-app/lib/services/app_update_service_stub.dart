import 'package:flutter/foundation.dart';

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
  Future<String> currentVersion() async => '0.0.0';

  Future<ApkUpdateInfo> fetchLatest({
    Duration timeout = const Duration(seconds: 20),
  }) async {
    throw UnsupportedError('Actualización de APK no disponible en esta plataforma.');
  }

  Future<ApkDownloadResult> downloadUpdate(
    ApkUpdateInfo info, {
    ApkProgressCb? progress,
  }) async {
    return const ApkDownloadResult(
      success: false,
      message: 'Actualización de APK no disponible en esta plataforma.',
    );
  }

  Future<bool> openInstaller(String apkPath) async => false;
}
