import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/utils/stream_memo.dart';

void main() {
  test('reutiliza el mismo Stream mientras la clave no cambia', () {
    final memo = StreamMemo<String, int>();
    var created = 0;

    Stream<int> create() {
      created++;
      return const Stream<int>.empty();
    }

    final first = memo.remember('uid-1', create);
    final second = memo.remember('uid-1', create);

    expect(identical(first, second), isTrue);
    expect(created, 0, reason: 'la fuente no se crea hasta el primer listener');
  });

  test('crea un Stream nuevo cuando cambia la clave', () {
    final memo = StreamMemo<String, int>();

    final first = memo.remember('uid-1', () => const Stream<int>.empty());
    final second = memo.remember('uid-2', () => const Stream<int>.empty());

    expect(identical(first, second), isFalse);
  });

  test('varios listeners comparten una sola suscripción a la fuente', () async {
    final memo = StreamMemo<String, int>();
    var sourceListens = 0;

    final stream = memo.remember('k', () {
      sourceListens++;
      return Stream<int>.fromIterable([1, 2]);
    });

    final first = <int>[];
    final second = <int>[];
    final sub1 = stream.listen(first.add);
    final sub2 = stream.listen(second.add);

    await Future<void>.delayed(Duration.zero);
    expect(sourceListens, 1);
    expect(first, [1, 2]);
    expect(second, [1, 2]);

    await sub1.cancel();
    await sub2.cancel();
  });
}
