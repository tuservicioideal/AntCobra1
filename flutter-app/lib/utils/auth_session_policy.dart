enum ProfileFailureReason { loadError, disabled, missingRole, missingProfile }

/// Un fallo transitorio (red, timeout, Firestore) no debe hacer signOut:
/// eso devuelve al login a los pocos segundos con el formulario aún lleno.
bool shouldSignOutAfterProfileFailure({required ProfileFailureReason reason}) {
  return reason != ProfileFailureReason.loadError;
}
