import 'dart:async';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'location_service.dart';

/// Continuous GPS tracking service for the Flutter app.
///
/// Strategy — "Smart continuous tracking" (FREE):
///   1. Uses Geolocator.getPositionStream() with distanceFilter = 10m
///   2. Only records a point if moved > 30m from last recorded point
///   3. Heartbeat: records at least once every 2 minutes (even if stationary)
///   4. Batches writes to Firestore every 60 seconds to minimize write count
///   5. Always keeps a "last known position" summary doc updated
class TrackingService extends ChangeNotifier {
  static final TrackingService _instance = TrackingService._internal();
  factory TrackingService() => _instance;
  TrackingService._internal();

  static const double _minDistanceMeters = 30.0;
  static const Duration _heartbeat = Duration(minutes: 2);
  static const Duration _batchInterval = Duration(seconds: 60);
  static const int _maxBufferSize = 50;

  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final LocationService _location = LocationService();

  StreamSubscription<Position>? _positionSub;
  Timer? _batchTimer;
  Timer? _heartbeatTimer;

  double? _lastRecordedLat;
  double? _lastRecordedLng;
  DateTime _lastRecordedTime = DateTime.fromMillisecondsSinceEpoch(0);
  Position? _currentPosition;
  final List<Map<String, dynamic>> _buffer = [];

  String _gestorUid = '';
  String _seccion = '';
  String _gestorName = '';
  bool _running = false;
  String? _error;

  bool get isRunning => _running;
  String? get error => _error;
  Position? get currentPosition => _currentPosition;
  int get pendingBufferSize => _buffer.length;

  /// Start continuous GPS tracking for the given gestor.
  Future<void> start({
    required String gestorUid,
    String seccion = '',
    String gestorName = '',
  }) async {
    if (_running) return;
    if (gestorUid.isEmpty) return;
    if (kIsWeb) {
      debugPrint(
        '[TrackingService] Web: seguimiento solo con la pestaña activa (sin segundo plano).',
      );
    }

    _gestorUid = gestorUid;
    _seccion = seccion;
    _gestorName = gestorName;
    _error = null;

    final ready = await _location.ensureReady();
    if (!ready) {
      _error = _location.error ?? 'No se pudo activar el GPS';
      debugPrint('[TrackingService] $_error');
      notifyListeners();
      return;
    }

    _running = true;
    _lastRecordedLat = null;
    _lastRecordedLng = null;
    _lastRecordedTime = DateTime.fromMillisecondsSinceEpoch(0);
    _buffer.clear();

    // Primera posición para que el mapa admin tenga datos de inmediato
    try {
      final initial = await _location.getCurrentPosition();
      if (initial != null) {
        _currentPosition = initial;
        _addToBuffer(initial);
        await _flushBuffer();
      }
    } catch (e) {
      debugPrint('[TrackingService] Initial position: $e');
    }

    final locationSettings = _location.streamSettings(background: !kIsWeb);

    _positionSub = Geolocator.getPositionStream(
      locationSettings: locationSettings,
    ).listen(
      _onPosition,
      onError: (e) {
        debugPrint('[TrackingService] Stream error: $e');
        _error = 'Error de GPS: $e';
        notifyListeners();
      },
    );

    _batchTimer = Timer.periodic(_batchInterval, (_) => _flushBuffer());

    _heartbeatTimer = Timer.periodic(_heartbeat, (_) {
      if (_currentPosition != null) {
        final sinceLastRecord = DateTime.now().difference(_lastRecordedTime);
        if (sinceLastRecord >= _heartbeat) {
          _addToBuffer(_currentPosition!);
        }
      }
    });

    debugPrint('[TrackingService] Started for $gestorUid ($gestorName)');
    notifyListeners();
  }

  Future<void> stop() async {
    if (!_running) return;
    _running = false;

    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    _batchTimer?.cancel();
    _batchTimer = null;
    await _positionSub?.cancel();
    _positionSub = null;

    await _flushBuffer();

    _currentPosition = null;
    _gestorUid = '';
    debugPrint('[TrackingService] Stopped');
    notifyListeners();
  }

  void _onPosition(Position position) {
    _currentPosition = position;

    final shouldRecord = _lastRecordedLat == null ||
        _haversineMeters(
              _lastRecordedLat!,
              _lastRecordedLng!,
              position.latitude,
              position.longitude,
            ) >=
            _minDistanceMeters;

    if (shouldRecord) {
      _addToBuffer(position);
    }
  }

  void _addToBuffer(Position position) {
    _lastRecordedLat = position.latitude;
    _lastRecordedLng = position.longitude;
    _lastRecordedTime = DateTime.now();

    final now = DateTime.now();
    _buffer.add({
      'lat': position.latitude,
      'lng': position.longitude,
      'accuracy': position.accuracy,
      'timestamp': FieldValue.serverTimestamp(),
      'fecha': now.toIso8601String(),
      'fecha_dia': _formatFechaDia(now),
      'seccion': _seccion,
      'gestor_nombre': _gestorName,
      'tipo': 'auto',
    });

    if (_buffer.length >= _maxBufferSize) {
      _flushBuffer();
    }
  }

  Future<void> _flushBuffer() async {
    if (_buffer.isEmpty || _gestorUid.isEmpty) return;

    final points = List<Map<String, dynamic>>.from(_buffer);
    _buffer.clear();

    try {
      final batch = _db.batch();
      final trackRef = _db.collection('ubicaciones_gestores').doc(_gestorUid);
      final puntosRef = trackRef.collection('puntos');

      for (final point in points) {
        batch.set(puntosRef.doc(), point);
      }

      final last = points.last;
      batch.set(
        trackRef,
        {
          'ultima_lat': last['lat'],
          'ultima_lng': last['lng'],
          'ultima_accuracy': last['accuracy'],
          'ultimo_timestamp': FieldValue.serverTimestamp(),
          'seccion': _seccion,
          'gestor_nombre': _gestorName,
          'ultimo_tipo': 'auto',
        },
        SetOptions(merge: true),
      );

      await batch.commit();
      debugPrint(
          '[TrackingService] Flushed ${points.length} points to Firestore');
    } catch (e) {
      debugPrint('[TrackingService] Error flushing buffer: $e');
      _buffer.insertAll(0, points);
    }
  }

  static double _haversineMeters(
      double lat1, double lng1, double lat2, double lng2) {
    const r = 6371000.0;
    final dLat = _toRad(lat2 - lat1);
    final dLng = _toRad(lng2 - lng1);
    final a = sin(dLat / 2) * sin(dLat / 2) +
        cos(_toRad(lat1)) * cos(_toRad(lat2)) * sin(dLng / 2) * sin(dLng / 2);
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));
    return r * c;
  }

  static double _toRad(double deg) => deg * pi / 180;

  static String _formatFechaDia(DateTime dt) {
    final y = dt.year;
    final m = dt.month.toString().padLeft(2, '0');
    final d = dt.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }
}
