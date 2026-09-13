import 'dart:async';

/// Reuses a Firestore [Stream] while [key] is unchanged so [StreamBuilder]
/// does not tear down the listen on every rebuild (that races Watch / ca9).
///
/// The returned stream is broadcast: several widgets can listen at once, and
/// the source is started on the first listener and cancelled on the last.
class StreamMemo<K, T> {
  K? _key;
  Stream<T>? _stream;
  StreamController<T>? _controller;
  StreamSubscription<T>? _subscription;
  Stream<T> Function()? _create;

  Stream<T> remember(K key, Stream<T> Function() create) {
    if (_stream != null && _key == key) return _stream!;
    _detach();
    _key = key;
    _create = create;
    _controller = StreamController<T>.broadcast(
      onListen: _startSource,
      onCancel: _stopSource,
    );
    _stream = _controller!.stream;
    return _stream!;
  }

  void _startSource() {
    final create = _create;
    if (create == null) return;
    _subscription = create().listen(
      (event) => _controller?.add(event),
      onError: (Object error, StackTrace stack) {
        _controller?.addError(error, stack);
      },
    );
  }

  void _stopSource() {
    _subscription?.cancel();
    _subscription = null;
  }

  void _detach() {
    _stopSource();
    _controller?.close();
    _controller = null;
    _stream = null;
    _create = null;
  }
}
