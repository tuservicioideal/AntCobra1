import '../models/client_model.dart';
import '../models/contact_metrics.dart';

bool isContactoEfectivo(ClientModel c) {
  if (c.nivel1 == 'Contacto efectivo') return true;
  return c.estadoGestion == 'visitado_habido';
}

bool isSmsEnviado(ClientModel c) {
  final n4 = c.nivel4.toLowerCase();
  return c.canalGestion == 'TEL' && n4.contains('sms');
}

bool isWspEnviado(ClientModel c) {
  final n4 = c.nivel4.toLowerCase();
  return c.canalGestion == 'TEL' && n4.contains('wsp');
}

bool isMailingEnviado(ClientModel c) {
  final n4 = c.nivel4.toLowerCase();
  return c.canalGestion == 'TEL' && n4.contains('mailing');
}

bool isVirtualEnviado(ClientModel c) =>
    isSmsEnviado(c) || isWspEnviado(c) || isMailingEnviado(c);

bool isLlamadaSinRespuesta(ClientModel c) {
  final n4 = c.nivel4.toLowerCase();
  if (c.canalGestion != 'TEL') return false;
  return n4.contains('grabadora') ||
      n4.contains('no contesta') ||
      n4.contains('ocupado') ||
      n4.contains('llamada fallida') ||
      n4.contains('apagado') ||
      n4.contains('fuera de servicio');
}

bool isPromesaCanal(ClientModel c, String canal) =>
    c.hasPromesa && c.canalGestion == canal;

/// Computes contact/channel KPIs from active clients.
ContactMetrics computeContactMetrics(List<ClientModel> clients) {
  var total = 0;
  var pendientes = 0;
  var totalGestionados = 0;
  var contactoEfectivo = 0;
  var contactoNoEfectivo = 0;
  var noContacto = 0;
  var canalTel = 0;
  var canalCam = 0;
  var contactoEfectivoTel = 0;
  var smsEnviados = 0;
  var wspEnviados = 0;
  var mailingEnviados = 0;
  var virtualConRespuesta = 0;
  var llamadaSinRespuesta = 0;
  var promesasTel = 0;
  var promesasCam = 0;

  for (final c in clients) {
    if (!c.isActiveForGestor) continue;
    total++;

    if (c.isPendiente) {
      pendientes++;
      continue;
    }

    totalGestionados++;

    if (isContactoEfectivo(c)) {
      contactoEfectivo++;
    } else if (c.nivel1 == 'Contacto no efectivo') {
      contactoNoEfectivo++;
    } else if (c.nivel1 == 'No contacto') {
      noContacto++;
    }

    if (c.canalGestion == 'TEL') {
      canalTel++;
      if (isContactoEfectivo(c)) contactoEfectivoTel++;
    } else if (c.canalGestion == 'CAM') {
      canalCam++;
    }

    if (isSmsEnviado(c)) smsEnviados++;
    if (isWspEnviado(c)) wspEnviados++;
    if (isMailingEnviado(c)) mailingEnviados++;
    if (isVirtualEnviado(c) && isContactoEfectivo(c)) virtualConRespuesta++;
    if (isLlamadaSinRespuesta(c)) llamadaSinRespuesta++;
    if (isPromesaCanal(c, 'TEL')) promesasTel++;
    if (isPromesaCanal(c, 'CAM')) promesasCam++;
  }

  return ContactMetrics(
    total: total,
    pendientes: pendientes,
    totalGestionados: totalGestionados,
    contactoEfectivo: contactoEfectivo,
    contactoNoEfectivo: contactoNoEfectivo,
    noContacto: noContacto,
    canalTel: canalTel,
    canalCam: canalCam,
    contactoEfectivoTel: contactoEfectivoTel,
    smsEnviados: smsEnviados,
    wspEnviados: wspEnviados,
    mailingEnviados: mailingEnviados,
    virtualConRespuesta: virtualConRespuesta,
    llamadaSinRespuesta: llamadaSinRespuesta,
    promesasTel: promesasTel,
    promesasCam: promesasCam,
  );
}

/// Matches clients for admin search (name, DNI, code, phone).
bool clientMatchesSearchQuery(ClientModel c, String query) {
  if (query.length < 2) return false;
  final q = query.toLowerCase().trim();
  return c.displayName.toLowerCase().contains(q) ||
      c.nombreCompleto.toLowerCase().contains(q) ||
      c.numeroDocumento.toLowerCase().contains(q) ||
      c.codigoCliente.toLowerCase().contains(q) ||
      c.telefonoMovil.toLowerCase().contains(q);
}
