/// Constantes y helpers del embudo de problemas (rol resolutor).
library;

const casoTipos = [
  'suplantacion',
  'pago_no_registrado',
  'no_hizo_pedido',
  'completo_pedido_socia',
];

const casoEtapas = [
  'nuevo',
  'en_gestion',
  'esperando_respuesta',
  'resuelto',
  'no_procede',
];

const casoEtapasAbiertas = [
  'nuevo',
  'en_gestion',
  'esperando_respuesta',
];

const casoEtapasCerradas = [
  'resuelto',
  'no_procede',
];

const casoTipoLabels = {
  'suplantacion': 'Suplantación',
  'pago_no_registrado': 'Pago no registrado',
  'no_hizo_pedido': 'No hizo pedido',
  'completo_pedido_socia': 'Completó el pedido la socia',
};

const casoEtapaLabels = {
  'nuevo': 'Nuevo',
  'en_gestion': 'En gestión',
  'esperando_respuesta': 'Esperando respuesta',
  'resuelto': 'Resuelto',
  'no_procede': 'No procede',
};

bool isCasoTipo(String? tipo) =>
    tipo != null && casoTipos.contains(tipo);

bool isCasoEtapa(String? etapa) =>
    etapa != null && casoEtapas.contains(etapa);

bool isEtapaAbierta(String etapa) => casoEtapasAbiertas.contains(etapa);

bool isEtapaCerrada(String etapa) => casoEtapasCerradas.contains(etapa);

String casoTipoLabel(String tipo) =>
    casoTipoLabels[tipo] ?? tipo;

String casoEtapaLabel(String etapa) =>
    casoEtapaLabels[etapa] ?? etapa;

/// Mapea nivel_3 del catálogo de reclamos a un tipo de caso (red de seguridad).
String? casoTipoFromNivel3(String? nivel3) {
  if (nivel3 == null || nivel3.trim().isEmpty) return null;
  final n = nivel3.trim().toLowerCase();
  if (n.contains('no hizo pedido')) return 'no_hizo_pedido';
  if (n.contains('completo pedido socia') ||
      n.contains('completó el pedido la socia') ||
      n.contains('completo pedido')) {
    return 'completo_pedido_socia';
  }
  return null;
}

/// Transiciones permitidas en el embudo (cualquier etapa abierta ↔ cerrada).
bool canMoveCasoEtapa(String from, String to) {
  if (!isCasoEtapa(from) || !isCasoEtapa(to)) return false;
  if (from == to) return false;
  return true;
}
