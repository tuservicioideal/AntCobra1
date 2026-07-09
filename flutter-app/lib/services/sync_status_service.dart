import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';

import 'connectivity_service.dart';
import 'tracking_service.dart';

/// Estado de sincronización visible en la shell (offline + cola GPS/visitas).
class SyncStatusService extends ChangeNotifier {
  SyncStatusService(this._connectivity, this._tracking) {
    _connectivity.addListener(_onChange);
    _tracking.addListener(_onChange);
    _syncSub = FirebaseFirestore.instance.snapshotsInSync().listen((_) {
      _pendingClientWrites = 0;
      notifyListeners();
    });
  }

  final ConnectivityService _connectivity;
  final TrackingService _tracking;
  StreamSubscription<void>? _syncSub;
  int _pendingClientWrites = 0;

  bool get isOnline => _connectivity.isOnline;

  int get pendingCount => _tracking.pendingBufferSize + _pendingClientWrites;

  bool get showSyncBanner => !isOnline || pendingCount > 0;

  String get bannerMessage {
    if (!isOnline) {
      if (pendingCount > 0) {
        return 'Sin conexión — $pendingCount pendiente(s) de subir';
      }
      return 'Sin conexión — modo offline';
    }
    if (pendingCount > 0) {
      return 'Subiendo $pendingCount cambio(s) pendiente(s)…';
    }
    return '';
  }

  void markClientWritePending() {
    _pendingClientWrites++;
    notifyListeners();
  }

  void _onChange() => notifyListeners();

  @override
  void dispose() {
    _connectivity.removeListener(_onChange);
    _tracking.removeListener(_onChange);
    _syncSub?.cancel();
    super.dispose();
  }
}
