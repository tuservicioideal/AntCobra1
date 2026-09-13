import 'package:flutter_test/flutter_test.dart';

import 'package:app_recaudo_legal/utils/auth_session_policy.dart';

void main() {
  test('un error de red no debe cerrar la sesión', () {
    expect(
      shouldSignOutAfterProfileFailure(reason: ProfileFailureReason.loadError),
      isFalse,
    );
  });

  test('cuenta inactiva o sin rol sí cierra sesión', () {
    expect(
      shouldSignOutAfterProfileFailure(reason: ProfileFailureReason.disabled),
      isTrue,
    );
    expect(
      shouldSignOutAfterProfileFailure(reason: ProfileFailureReason.missingRole),
      isTrue,
    );
    expect(
      shouldSignOutAfterProfileFailure(reason: ProfileFailureReason.missingProfile),
      isTrue,
    );
  });
}
