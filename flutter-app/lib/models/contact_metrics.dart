/// Aggregated contact / channel response metrics for executive dashboards.
class ContactMetrics {
  final int total;
  final int pendientes;
  final int totalGestionados;
  final int contactoEfectivo;
  final int contactoNoEfectivo;
  final int noContacto;
  final int canalTel;
  final int canalCam;
  final int contactoEfectivoTel;
  final int smsEnviados;
  final int wspEnviados;
  final int mailingEnviados;
  final int virtualConRespuesta;
  final int llamadaSinRespuesta;
  final int promesasTel;
  final int promesasCam;

  const ContactMetrics({
    this.total = 0,
    this.pendientes = 0,
    this.totalGestionados = 0,
    this.contactoEfectivo = 0,
    this.contactoNoEfectivo = 0,
    this.noContacto = 0,
    this.canalTel = 0,
    this.canalCam = 0,
    this.contactoEfectivoTel = 0,
    this.smsEnviados = 0,
    this.wspEnviados = 0,
    this.mailingEnviados = 0,
    this.virtualConRespuesta = 0,
    this.llamadaSinRespuesta = 0,
    this.promesasTel = 0,
    this.promesasCam = 0,
  });

  double get pctContactoEfectivo =>
      totalGestionados > 0 ? contactoEfectivo / totalGestionados * 100 : 0;

  double get pctRespuestaTel =>
      canalTel > 0 ? contactoEfectivoTel / canalTel * 100 : 0;

  int get virtualEnviados => smsEnviados + wspEnviados + mailingEnviados;

  double get pctVirtualSeguimiento =>
      virtualEnviados > 0 ? virtualConRespuesta / virtualEnviados * 100 : 0;

  double get pctCanalTel =>
      totalGestionados > 0 ? canalTel / totalGestionados * 100 : 0;

  double get pctCanalCam =>
      totalGestionados > 0 ? canalCam / totalGestionados * 100 : 0;
}
