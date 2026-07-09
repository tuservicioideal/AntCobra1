const REQUIRED_PLACEHOLDERS = [
  'NOMBRE',
  'DNI',
  'DIRECCION',
  'CODIGO',
  'ZONA',
  'SECCION',
  'CAMPANA',
  'DEUDA',
  'CODIGO_PAGO',
  'FECHA',
  'FECHA_VENCIMIENTO',
];

const TITLE_BY_TEMPLATE = {
  1: 'INVITACION A REINGRESO',
  2: 'NO PIERDAS SER EMPRESARIA',
  3: 'REQUERIMIENTO DE PAGO',
  4: 'INSISTENCIA DE PAGO - REQUERIMIENTO URGENTE',
  5: 'EXIGIMOS PAGO - ETAPA PRE-JUDICIAL',
};

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function paragraphs(lines) {
  return lines.map((line) => `<p>${line}</p>`).join('');
}

export function getLetterTemplateHtml({
  templateId,
  placeholders,
  watermarkUrl = '',
}) {
  const title = TITLE_BY_TEMPLATE[templateId] || TITLE_BY_TEMPLATE[1];
  const wmBlock = watermarkUrl
    ? `<img class="wm" src="${esc(watermarkUrl)}" alt="" />`
    : '';

  const infoLine = `
    <p><b>Señor(a):</b> ${esc(placeholders.NOMBRE)}&nbsp;&nbsp;&nbsp;<b>DNI:</b> ${esc(placeholders.DNI)}</p>
    <p><b>Dirección:</b> ${esc(placeholders.DIRECCION)}</p>
    <p><b>Código:</b> ${esc(placeholders.CODIGO)}&nbsp;&nbsp;<b>Zona:</b> ${esc(placeholders.ZONA)}&nbsp;&nbsp;<b>Sección:</b> ${esc(placeholders.SECCION)}&nbsp;&nbsp;<b>Campaña:</b> ${esc(placeholders.CAMPANA)}</p>
  `;

  const bodyByTemplate = {
    1: paragraphs([
      'Estimado(a) Consultor(a):',
      '<b>Reciba un cordial saludo.</b>',
      'Nos comunicamos con usted para invitarle a retomar su desarrollo empresarial dentro de BELCORP (Esika, L\'Bel y Cyzone).',
      'Tenemos una <span class="red"><b>oportunidad de reingreso inmediato</b></span> para que continúe creciendo con nosotros.',
      `Podra regularizar su saldo por <b>S/ ${esc(placeholders.DEUDA)}</b> sin recargos adicionales.`,
      'Puede realizar su pago mediante banca por internet, billeteras digitales, apps bancarias o tarjeta en la web oficial.',
      `<p class="pay-code"><b>CODIGO DE PAGO: ${esc(placeholders.CODIGO_PAGO)}  DEUDA PENDIENTE: S/ ${esc(placeholders.DEUDA)}</b></p>`,
      'Agradecemos su atencion y confianza.',
    ]),
    2: paragraphs([
      'Estimado(a) Consultor(a):',
      '<b>Reciba un cordial saludo.</b>',
      'Reiteramos la invitacion especial para retomar su actividad comercial con BELCORP.',
      'Le brindamos una <span class="red"><b>segunda oportunidad de reingreso</b></span>.',
      `Solo necesita regularizar su saldo por <b>S/ ${esc(placeholders.DEUDA)}</b>.`,
      `<p class="pay-code"><b>CODIGO DE PAGO: ${esc(placeholders.CODIGO_PAGO)}  DEUDA PENDIENTE: S/ ${esc(placeholders.DEUDA)}</b></p>`,
      'Tras el pago, su reincorporacion al area comercial sera inmediata.',
    ]),
    3: paragraphs([
      'Estimado(a) Consultor(a):',
      '<b>Reciba un cordial saludo.</b>',
      'Le recordamos que mantiene un saldo pendiente asociado a su cuenta BELCORP.',
      `Registra una deuda de <b>S/ ${esc(placeholders.DEUDA)}</b>, con vencimiento ${esc(placeholders.FECHA_VENCIMIENTO)}.`,
      'Le solicitamos regularizar esta obligacion para evitar reportes a centrales de riesgo.',
      '<span class="red"><b>Plazo maximo: 72 horas.</b></span>',
    ]),
    4: paragraphs([
      'Estimado(a) Consultor(a):',
      '<b>Reciba un cordial saludo.</b>',
      'Su obligacion pendiente permanece impaga pese a comunicaciones previas.',
      'Su cuenta ya registra acciones en centrales de riesgo como Infocorp y Camara de Comercio de Lima.',
      `Le solicitamos regularizar el pago total de <b>S/ ${esc(placeholders.DEUDA)}</b>.`,
      '<span class="red"><b>Plazo maximo: 48 horas.</b></span>',
    ]),
    5: paragraphs([
      'Estimado(a) Consultor(a):',
      'Nos dirigimos a usted por su obligacion pendiente de pago con CETCO S.A. - BELCORP.',
      'Su cuenta se encuentra reportada a centrales de riesgo, afectando su historial.',
      `Se requiere la cancelacion total de <b>S/ ${esc(placeholders.DEUDA)}</b> dentro de un plazo perentorio.`,
      '<span class="red"><b>Plazo maximo e improrrogable: 48 horas.</b></span>',
      'De no regularizar, se iniciaran acciones de cobranza judicial.',
    ]),
  };

  return `
    <div class="letter-page">
      ${wmBlock}
      <h1>${title}</h1>
      <div class="date">Lima, ${esc(placeholders.FECHA)}</div>
      <div class="block">${infoLine}</div>
      <div class="block">${bodyByTemplate[templateId] || bodyByTemplate[1]}</div>
      <div class="block">
        <p>Atentamente,</p>
        <p><b>RECAUDO LEGAL & ABOGADOS</b></p>
        <p>WhatsApp: 942 470 641</p>
        <p>Email: recaudolegal@yahoo.com</p>
        <p><b>Encargado:</b> ${esc(placeholders.GESTOR_NOMBRE)} &nbsp;&nbsp; <b>Celular:</b> ${esc(placeholders.GESTOR_CELULAR)}</p>
      </div>
      <div class="note">
        Nota: Si usted ya realizo el pago, sirvase omitir este comunicado.
      </div>
    </div>
  `;
}

export function getLetterCss() {
  return `
    .letter-page{
      position:relative;
      width:1240px;
      min-height:1754px;
      background:#fff;
      color:#111;
      font-family:Arial, Helvetica, sans-serif;
      padding:72px 72px 48px 72px;
      box-sizing:border-box;
    }
    .wm{
      position:absolute;
      left:50%;
      top:52%;
      transform:translate(-50%,-50%);
      width:60%;
      opacity:0.16;
      pointer-events:none;
      z-index:0;
    }
    h1,.date,.block,.note{position:relative;z-index:1;}
    h1{
      margin:0 0 24px;
      text-align:center;
      color:#d00000;
      text-decoration:underline;
      font-size:52px;
      line-height:1.06;
      letter-spacing:0.5px;
      font-weight:800;
      text-transform:uppercase;
    }
    .date{
      text-align:right;
      font-size:31px;
      font-weight:700;
      margin-bottom:26px;
    }
    .block{margin-bottom:24px;}
    .block p{
      margin:0 0 10px;
      font-size:30px;
      line-height:1.3;
    }
    .red{color:#d10000;}
    .pay-code{
      text-align:center;
      font-size:34px !important;
      margin-top:18px !important;
    }
    .note{
      margin-top:18px;
      font-size:22px;
      line-height:1.3;
    }
  `;
}

export function validatePlaceholders(placeholders) {
  const missing = REQUIRED_PLACEHOLDERS.filter((key) => !String(placeholders?.[key] ?? '').trim());
  return {
    ok: missing.length === 0,
    missing,
  };
}

export function mapClientToPlaceholders({
  client,
  gestorName = '',
  gestorPhone = '',
  campaignName = '',
}) {
  const amount = Number(client.importe_deuda_pendiente || client.importe_deuda_asignada || 0);
  const date = new Date();
  const fecha = date.toLocaleDateString('es-PE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
  return {
    NOMBRE: client.nombre_completo || [client.nombres, client.apellido_paterno, client.apellido_materno].filter(Boolean).join(' '),
    DNI: String(client.numero_documento || ''),
    DIRECCION: [client.direccion, client.distrito, client.provincia, client.departamento].filter(Boolean).join(', '),
    CODIGO: String(client.codigo_cliente || ''),
    ZONA: String(client.zona || ''),
    SECCION: String(client.seccion || ''),
    CAMPANA: campaignName || String(client.campana || 'Cartera activa'),
    DEUDA: amount.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    CODIGO_PAGO: String(client.codigo_cliente || client.codigo_pago || ''),
    FECHA: fecha,
    FECHA_VENCIMIENTO: String(client.fecha_vencimiento || '—'),
    GESTOR_NOMBRE: gestorName || 'Gestor asignado',
    GESTOR_CELULAR: gestorPhone || 'No consignado',
  };
}
