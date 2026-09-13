const maxExcelBytes = 50 * 1024 * 1024;
const androidWarnBytes = 8 * 1024 * 1024;

String? validateExcelFileName(String name) {
  final lower = name.toLowerCase().trim();
  if (lower.endsWith('.xlsx') || lower.endsWith('.xlsm')) return null;
  return 'El archivo debe ser .xlsx o .xlsm';
}

bool shouldWarnLargeFile({required bool isWeb, required int bytes}) {
  return !isWeb && bytes > androidWarnBytes;
}

bool exceedsMaxExcelSize(int bytes) => bytes > maxExcelBytes;

bool canConfirmPublish({
  required String estado,
  required int totalClientes,
  required List<String> seccionesSinGestor,
  required bool forceSinGestor,
}) {
  if (estado != 'preview') return false;
  if (totalClientes < 1) return false;
  if (seccionesSinGestor.isNotEmpty && !forceSinGestor) return false;
  return true;
}

String jobEstadoLabel(String estado) {
  switch (estado) {
    case 'subiendo':
      return 'Subiendo archivo';
    case 'parseando':
      return 'Analizando Excel';
    case 'preview':
      return 'Listo para confirmar';
    case 'publicando':
      return 'Publicando cartera';
    case 'listo':
      return 'Cartera publicada';
    case 'error':
      return 'Error';
    case 'cancelado':
      return 'Cancelado';
    default:
      return estado;
  }
}
