import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';

/// Servicio centralizado de GPS (móvil y web).
class LocationService extends ChangeNotifier {
  static final LocationService _instance = LocationService._internal();
  factory LocationService() => _instance;
  LocationService._internal();

  Position? _lastPosition;
  String? _error;
  bool _permissionReady = false;

  Position? get lastPosition => _lastPosition;
  double? get latitude => _lastPosition?.latitude;
  double? get longitude => _lastPosition?.longitude;
  String? get error => _error;
  bool get hasPosition => _lastPosition != null;
  bool get permissionReady => _permissionReady;

  bool get _isAndroid =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
  bool get _isIOS => !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;

  Future<bool> ensureReady({bool requestIfNeeded = true}) async {
    _error = null;

    var serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      _error = kIsWeb
          ? 'Active la ubicación en el navegador o dispositivo.'
          : 'Active el GPS del dispositivo en Configuración.';
      _permissionReady = false;
      notifyListeners();
      return false;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied && requestIfNeeded) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.denied) {
      _error = kIsWeb
          ? 'Permiso de ubicación denegado. Permítalo en el navegador.'
          : 'Permiso de ubicación denegado.';
      _permissionReady = false;
      notifyListeners();
      return false;
    }

    if (permission == LocationPermission.deniedForever) {
      _error = kIsWeb
          ? 'Ubicación bloqueada. Revise los permisos del sitio en el navegador.'
          : 'Permiso de ubicación bloqueado. Actívelo en Configuración de la app.';
      _permissionReady = false;
      notifyListeners();
      return false;
    }

    if (_isAndroid) {
      await _requestAndroidNotificationPermission();
    }

    _permissionReady = true;
    notifyListeners();
    return true;
  }

  Future<Position?> getCurrentPosition({bool requestPermission = true}) async {
    try {
      _error = null;

      final ready = await ensureReady(requestIfNeeded: requestPermission);
      if (!ready) return null;

      Position? position;

      try {
        position = await Geolocator.getCurrentPosition(
          locationSettings: _settingsForCurrentPosition(highAccuracy: true),
        );
      } on TimeoutException {
        position = null;
      } catch (e) {
        debugPrint('[LocationService] High accuracy failed: $e');
        position = null;
      }

      if (position == null) {
        try {
          position = await Geolocator.getCurrentPosition(
            locationSettings: _settingsForCurrentPosition(highAccuracy: false),
          );
        } catch (e) {
          debugPrint('[LocationService] Medium accuracy failed: $e');
        }
      }

      position ??= await Geolocator.getLastKnownPosition();

      if (position == null) {
        _error = kIsWeb
            ? 'No se pudo obtener la ubicación. Compruebe permisos del navegador.'
            : 'No se pudo obtener la ubicación. Intente al aire libre o reintente.';
        notifyListeners();
        return null;
      }

      _lastPosition = position;
      notifyListeners();
      return _lastPosition;
    } catch (e) {
      debugPrint('[LocationService] Error: $e');
      _error = _humanizeError(e);
      notifyListeners();
      return null;
    }
  }

  LocationSettings streamSettings({bool background = false}) {
    if (kIsWeb) {
      return const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
      );
    }
    if (_isAndroid) {
      return AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
        intervalDuration: const Duration(seconds: 15),
        foregroundNotificationConfig: background
            ? const ForegroundNotificationConfig(
                notificationTitle: 'Recaudo Legal',
                notificationText: 'Registrando ubicación en campo',
                notificationIcon: AndroidResource(
                  name: 'ic_launcher',
                  defType: 'mipmap',
                ),
                enableWakeLock: true,
              )
            : null,
      );
    }
    if (_isIOS) {
      return AppleSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
        showBackgroundLocationIndicator: background,
      );
    }
    return const LocationSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: 10,
    );
  }

  LocationSettings _settingsForCurrentPosition({required bool highAccuracy}) {
    final accuracy =
        highAccuracy ? LocationAccuracy.high : LocationAccuracy.medium;
    final timeLimit = Duration(seconds: highAccuracy ? 25 : 15);

    if (_isAndroid) {
      return AndroidSettings(
        accuracy: accuracy,
        timeLimit: timeLimit,
      );
    }
    if (_isIOS) {
      return AppleSettings(
        accuracy: accuracy,
        timeLimit: timeLimit,
      );
    }
    return LocationSettings(
      accuracy: accuracy,
      timeLimit: timeLimit,
    );
  }

  Future<void> _requestAndroidNotificationPermission() async {
    if (!_isAndroid) return;
    final status = await Permission.notification.status;
    if (status.isGranted || status.isPermanentlyDenied) return;
    await Permission.notification.request();
  }

  String _humanizeError(Object e) {
    final msg = e.toString().toLowerCase();
    if (msg.contains('timeout') || msg.contains('time limit')) {
      return kIsWeb
          ? 'Tiempo de espera agotado. Compruebe permisos de ubicación.'
          : 'Tiempo de espera agotado. Compruebe que el GPS está activo.';
    }
    if (msg.contains('permission') || msg.contains('denied')) {
      return 'Permiso de ubicación denegado.';
    }
    return 'Error al obtener ubicación: $e';
  }

  Future<bool> openAppSettings() => Geolocator.openAppSettings();

  Future<bool> openLocationSettings() => Geolocator.openLocationSettings();

  void clear() {
    _lastPosition = null;
    _error = null;
    _permissionReady = false;
    notifyListeners();
  }
}
