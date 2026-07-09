/// Rules for when the APK shows monto/fecha fields during client management.
class GestionMontoRules {
  GestionMontoRules._();

  static bool requiresMontoPanel({
    required String n2,
    String n3 = '',
    String n4 = '',
  }) {
    final n2l = _norm(n2);
    if (n2l.isEmpty) return false;
    final blob = '$n2l ${_norm(n3)} ${_norm(n4)}';
    if (n2l.contains('promesa')) return true;
    if (n2l.contains('cliente cancelo') || n2l.contains('cliente canceló')) {
      return true;
    }
    if (blob.contains('pago a socia') ||
        blob.contains('pago a cobrador') ||
        blob.contains('pago a gerente')) {
      return true;
    }
    return false;
  }

  static bool showFechaField({required String n2}) {
    final n2l = _norm(n2);
    return n2l.contains('promesa de pago') || n2l.contains('recordar promesa');
  }

  static String panelTitle({required String n2, String n3 = ''}) {
    final n2l = _norm(n2);
    final n3l = _norm(n3);
    if (n2l.contains('cliente cancelo') || n2l.contains('cliente canceló')) {
      return 'Importe del pago';
    }
    if (n3l.contains('pago a socia') || n3l.contains('pago a')) {
      return 'Importe referido del pago';
    }
    if (n2l.contains('recordar promesa')) {
      return 'Promesa registrada';
    }
    return 'Promesa de pago';
  }

  static String montoLabel({required String n2, String n3 = ''}) {
    final n2l = _norm(n2);
    final n3l = _norm(n3);
    if (n2l.contains('cliente cancelo') || n2l.contains('cliente canceló')) {
      return 'Monto pagado (S/)';
    }
    if (n3l.contains('pago a socia') || n3l.contains('pago a')) {
      return 'Monto pagado (S/)';
    }
    if (n2l.contains('recordar promesa')) {
      return 'Monto prometido (S/)';
    }
    return 'Monto prometido (S/)';
  }

  static String montoHint(double deudaPendiente) {
    if (deudaPendiente <= 0) return 'Opcional';
    final formatted = deudaPendiente.toStringAsFixed(2);
    return 'Ref. deuda pendiente: S/ $formatted';
  }

  static String _norm(String s) => s.toLowerCase().trim();
}
