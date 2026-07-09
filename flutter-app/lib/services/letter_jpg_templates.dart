export 'letter_placeholders.dart' show
    LetterJpgPlaceholders,
    LetterPlaceholders,
    titleByTemplate,
    resolveTemplateId,
    mapClientToPlaceholders,
    validatePlaceholders,
    sanitizeName;

import 'letter_placeholders.dart';

List<String> bodyLinesForTemplate(int templateId, LetterPlaceholders p) {
  switch (templateId) {
    case 2:
      return [
        'Estimado(a) Consultor(a):',
        'Reciba un cordial saludo.',
        'Reiteramos la invitacion especial para retomar su actividad comercial con BELCORP.',
        'Le brindamos una segunda oportunidad de reingreso.',
        'Solo necesita regularizar su saldo por S/ ${p.deuda}.',
        'CODIGO DE PAGO: ${p.codigoPago}  DEUDA PENDIENTE: S/ ${p.deuda}',
        'Tras el pago, su reincorporacion al area comercial sera inmediata.',
      ];
    case 3:
      return [
        'Estimado(a) Consultor(a):',
        'Reciba un cordial saludo.',
        'Le recordamos que mantiene un saldo pendiente asociado a su cuenta BELCORP.',
        'Registra una deuda de S/ ${p.deuda}, con vencimiento ${p.fechaVencimiento}.',
        'Le solicitamos regularizar esta obligacion para evitar reportes a centrales de riesgo.',
        'Plazo maximo: 72 horas.',
      ];
    case 4:
      return [
        'Estimado(a) Consultor(a):',
        'Reciba un cordial saludo.',
        'Su obligacion pendiente permanece impaga pese a comunicaciones previas.',
        'Su cuenta ya registra acciones en centrales de riesgo como Infocorp y Camara de Comercio de Lima.',
        'Le solicitamos regularizar el pago total de S/ ${p.deuda}.',
        'Plazo maximo: 48 horas.',
      ];
    case 5:
      return [
        'Estimado(a) Consultor(a):',
        'Nos dirigimos a usted por su obligacion pendiente de pago con CETCO S.A. - BELCORP.',
        'Su cuenta se encuentra reportada a centrales de riesgo, afectando su historial.',
        'Se requiere la cancelacion total de S/ ${p.deuda} dentro de un plazo perentorio.',
        'Plazo maximo e improrrogable: 48 horas.',
        'De no regularizar, se iniciaran acciones de cobranza judicial.',
      ];
    default:
      return [
        'Estimado(a) Consultor(a):',
        'Reciba un cordial saludo.',
        'Nos comunicamos con usted para invitarle a retomar su desarrollo empresarial dentro de BELCORP (Esika, L\'Bel y Cyzone).',
        'Tenemos una oportunidad de reingreso inmediato para que continúe creciendo con nosotros.',
        'Podra regularizar su saldo por S/ ${p.deuda} sin recargos adicionales.',
        'Puede realizar su pago mediante banca por internet, billeteras digitales, apps bancarias o tarjeta en la web oficial.',
        'CODIGO DE PAGO: ${p.codigoPago}  DEUDA PENDIENTE: S/ ${p.deuda}',
        'Agradecemos su atencion y confianza.',
      ];
  }
}
