import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/utils/firestore_web_recovery.dart';

void main() {
  group('isFirestoreInternalAssertion', () {
    test('detecta ca9 y b815 del SDK JS', () {
      expect(
        isFirestoreInternalAssertion(
          'FIRESTORE (11.9.1) INTERNAL ASSERTION FAILED: Unexpected state (ID: ca9)',
        ),
        isTrue,
      );
      expect(
        isFirestoreInternalAssertion(
          'FIRESTORE (11.9.1) INTERNAL ASSERTION FAILED: Unexpected state (ID: b815)',
        ),
        isTrue,
      );
    });

    test('detecta ca9 en el stack aunque toString del Error sea vacío', () {
      expect(isFirestoreInternalAssertion('Error'), isFalse);
      expect(
        isFirestoreInternalAssertion(
          combineErrorSources([
            'Error',
            'FIRESTORE (11.9.1) INTERNAL ASSERTION FAILED: Unexpected state (ID: ca9) CONTEXT: {"Fe":-1}',
          ]),
        ),
        isTrue,
      );
    });

    test('detecta el log de consola y el ID suelto del Watch', () {
      expect(
        isFirestoreInternalAssertion(
          '@firebase/firestore: Unexpected state (ID: ca9) CONTEXT: {"Fe":-1}',
        ),
        isTrue,
      );
      expect(
        isFirestoreInternalAssertion('Unexpected state (ID: b815)'),
        isTrue,
      );
    });

    test('ignora errores de red o permisos normales', () {
      expect(isFirestoreInternalAssertion(null), isFalse);
      expect(isFirestoreInternalAssertion('permission-denied'), isFalse);
      expect(isFirestoreInternalAssertion(Exception('unavailable')), isFalse);
    });
  });

  test('solo recarga una vez por sesión', () {
    expect(
      shouldReloadAfterFirestoreAssertion(alreadyReloadedThisSession: false),
      isTrue,
    );
    expect(
      shouldReloadAfterFirestoreAssertion(alreadyReloadedThisSession: true),
      isFalse,
    );
  });
}
