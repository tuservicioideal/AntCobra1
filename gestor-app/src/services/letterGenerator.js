/**
 * Letter Generator — Client-side Word document generation
 * Generates professional collection letters as .docx files
 * that gestors can download directly from the web app.
 */

import {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, PageBreak,
  ShadingType
} from 'docx';
import { saveAs } from 'file-saver';

const COLORS = {
  primary: 'D00000',
  danger: 'DC2626',
  textDark: '111111',
  textMuted: '333333',
  border: 'E2E8F0',
  bgLight: 'F1F5F9',
};

const TITLE_BY_TEMPLATE = {
  1: 'INVITACION A REINGRESO',
  2: 'NO PIERDAS SER EMPRESARIA',
  3: 'REQUERIMIENTO DE PAGO',
  4: 'INSISTENCIA DE PAGO - REQUERIMIENTO URGENTE',
  5: 'EXIGIMOS PAGO - ETAPA PRE-JUDICIAL',
};

function formatCurrency(value) {
  const num = parseFloat(value) || 0;
  return `S/ ${num.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getSpanishDate() {
  const months = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
  ];
  const d = new Date();
  return `${d.getDate()} de ${months[d.getMonth()]} de ${d.getFullYear()}`;
}

function resolveTemplateId(client) {
  const numeroCarta = Number(client?.numero_carta || 0);
  if (numeroCarta >= 1 && numeroCarta <= 5) return numeroCarta;
  const tramo = Number(client?.tramo_actual || 1);
  if (tramo <= 1) return 1;
  if (tramo === 2) return 3;
  if (tramo >= 3) return 5;
  return 1;
}

function getTemplateParagraphs(templateId, deudaPendiente, fechaVencimiento, codigoCliente) {
  const byTemplate = {
    1: [
      'Estimado(a) Consultor(a):',
      'Reciba un cordial saludo.',
      'Nos comunicamos con usted para invitarle a retomar su desarrollo empresarial dentro de BELCORP (Esika, L Bel y Cyzone).',
      'Tenemos una oportunidad de reingreso inmediato para que continue creciendo con nosotros.',
      `Podra regularizar su saldo por ${deudaPendiente} sin recargos adicionales.`,
      'Puede realizar su pago mediante banca por internet, billeteras digitales, apps bancarias o tarjeta en la web oficial.',
      `CODIGO DE PAGO: ${codigoCliente}  DEUDA PENDIENTE: ${deudaPendiente}`,
      'Agradecemos su atencion y confianza.',
    ],
    2: [
      'Estimado(a) Consultor(a):',
      'Reciba un cordial saludo.',
      'Reiteramos la invitacion especial para retomar su actividad comercial con BELCORP.',
      'Le brindamos una segunda oportunidad de reingreso.',
      `Solo necesita regularizar su saldo por ${deudaPendiente}.`,
      `CODIGO DE PAGO: ${codigoCliente}  DEUDA PENDIENTE: ${deudaPendiente}`,
      'Tras el pago, su reincorporacion al area comercial sera inmediata.',
    ],
    3: [
      'Estimado(a) Consultor(a):',
      'Reciba un cordial saludo.',
      'Le recordamos que mantiene un saldo pendiente asociado a su cuenta BELCORP.',
      `Registra una deuda de ${deudaPendiente}, con vencimiento ${fechaVencimiento}.`,
      'Le solicitamos regularizar esta obligacion para evitar reportes a centrales de riesgo.',
      'Plazo maximo: 72 horas.',
    ],
    4: [
      'Estimado(a) Consultor(a):',
      'Reciba un cordial saludo.',
      'Su obligacion pendiente permanece impaga pese a comunicaciones previas.',
      'Su cuenta ya registra acciones en centrales de riesgo como Infocorp y Camara de Comercio de Lima.',
      `Le solicitamos regularizar el pago total de ${deudaPendiente}.`,
      'Plazo maximo: 48 horas.',
    ],
    5: [
      'Estimado(a) Consultor(a):',
      'Nos dirigimos a usted por su obligacion pendiente de pago con CETCO S.A. - BELCORP.',
      'Su cuenta se encuentra reportada a centrales de riesgo, afectando su historial.',
      `Se requiere la cancelacion total de ${deudaPendiente} dentro de un plazo perentorio.`,
      'Plazo maximo e improrrogable: 48 horas.',
      'De no regularizar, se iniciaran acciones de cobranza judicial.',
    ],
  };
  return byTemplate[templateId] || byTemplate[1];
}

function createLetterSection(client, seccion, gestorName) {
  const templateId = resolveTemplateId(client);
  const title = TITLE_BY_TEMPLATE[templateId] || TITLE_BY_TEMPLATE[1];
  const nombre = client.nombre_completo ||
    `${client.nombres || ''} ${client.apellido_paterno || ''} ${client.apellido_materno || ''}`.trim();
  const dni = client.numero_documento || '—';
  const direccion = [client.direccion, client.distrito, client.provincia, client.departamento]
    .filter(Boolean).join(', ');
  const telefono = client.telefono_movil || '';
  const deudaPendiente = formatCurrency(client.importe_deuda_pendiente);
  const deudaAsignada = formatCurrency(client.importe_deuda_asignada);
  const codigoCliente = String(client.codigo_cliente || '');
  const zona = String(client.zona || '');
  const campana = String(client.campana || 'Cartera activa');
  const fechaVencimiento = String(client.fecha_vencimiento || '—');
  const templateLines = getTemplateParagraphs(templateId, deudaPendiente, fechaVencimiento, codigoCliente);

  const children = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 80 },
      children: [
        new TextRun({
          text: title,
          bold: true,
          underline: {},
          size: 40,
          color: COLORS.primary,
          font: 'Arial',
        }),
      ],
    }),

    new Paragraph({
      alignment: AlignmentType.RIGHT,
      spacing: { after: 220 },
      children: [
        new TextRun({ text: `Lima, ${getSpanishDate()}`, size: 22, color: COLORS.textMuted, bold: true }),
      ],
    }),

    new Paragraph({
      spacing: { after: 70 },
      children: [
        new TextRun({ text: 'Señor(a): ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: nombre || '—', size: 22, font: 'Arial' }),
        new TextRun({ text: '   DNI: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: String(dni), size: 22, font: 'Arial' }),
      ],
    }),
    new Paragraph({
      spacing: { after: 70 },
      children: [
        new TextRun({ text: 'Direccion: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: direccion || '—', size: 22, font: 'Arial' }),
      ],
    }),
    new Paragraph({
      spacing: { after: 170 },
      children: [
        new TextRun({ text: 'Codigo: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: codigoCliente || '—', size: 22, font: 'Arial' }),
        new TextRun({ text: '  Zona: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: zona || '—', size: 22, font: 'Arial' }),
        new TextRun({ text: '  Seccion: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: seccion || '—', size: 22, font: 'Arial' }),
        new TextRun({ text: '  Campana: ', bold: true, size: 22, font: 'Arial' }),
        new TextRun({ text: campana, size: 22, font: 'Arial' }),
      ],
    }),
  ];

  templateLines.forEach((line) => {
    const isDeadline = line.toLowerCase().includes('plazo maximo');
    const isPayCode = line.toLowerCase().includes('codigo de pago');
    children.push(
      new Paragraph({
        alignment: isPayCode ? AlignmentType.CENTER : AlignmentType.LEFT,
        spacing: { after: isPayCode ? 150 : 90 },
        children: [
          new TextRun({
            text: line,
            size: isPayCode ? 24 : 22,
            bold: isPayCode || isDeadline,
            color: isDeadline ? COLORS.danger : COLORS.textDark,
            font: 'Arial',
          }),
        ],
      })
    );
  });

  const thinBorder = { style: BorderStyle.SINGLE, size: 1, color: COLORS.border };
  const tableRows = [
    ['Deuda Asignada', deudaAsignada],
    ['Deuda Pendiente', deudaPendiente],
    ['Fecha Vencimiento', fechaVencimiento],
    ['Telefono', telefono || '—'],
  ].map(([label, value]) =>
    new TableRow({
      children: [
        new TableCell({
          width: { size: 4500, type: WidthType.DXA },
          borders: { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder },
          shading: { type: ShadingType.SOLID, color: COLORS.bgLight },
          children: [new Paragraph({
            children: [new TextRun({ text: label, bold: true, size: 21, font: 'Calibri' })],
          })],
        }),
        new TableCell({
          width: { size: 4500, type: WidthType.DXA },
          borders: { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder },
          children: [new Paragraph({
            children: [new TextRun({ text: value, size: 21, font: 'Calibri' })],
          })],
        }),
      ],
    })
  );

  children.push(new Table({
    rows: tableRows,
    width: { size: 9000, type: WidthType.DXA },
  }));

  children.push(
    new Paragraph({ spacing: { before: 260, after: 100 }, children: [] }),
    new Paragraph({
      spacing: { after: 100 },
      children: [
        new TextRun({
          text: 'Atentamente,',
          size: 22,
          font: 'Arial',
        }),
      ],
    }),
    new Paragraph({
      spacing: { after: 70 },
      children: [
        new TextRun({
          text: 'RECAUDO LEGAL & ABOGADOS',
          size: 22,
          bold: true,
          font: 'Arial',
        }),
      ],
    }),
    new Paragraph({
      spacing: { after: 60 },
      children: [new TextRun({ text: 'WhatsApp: 942 470 641', size: 20, font: 'Arial' })],
    }),
    new Paragraph({
      spacing: { after: 60 },
      children: [new TextRun({ text: 'Email: recaudolegal@yahoo.com', size: 20, font: 'Arial' })],
    }),
  );

  children.push(
    new Paragraph({
      spacing: { after: 90 },
      children: [
        new TextRun({
          text: `Encargado: ${gestorName || 'Gestor asignado'}   Celular: ${telefono || 'No consignado'}`,
          size: 20,
          bold: true,
          font: 'Arial',
        }),
      ],
    }),
    new Paragraph({
      spacing: { after: 0 },
      children: [
        new TextRun({
          text: 'Nota: Si usted ya realizo el pago, sirvase omitir este comunicado.',
          size: 19,
          font: 'Arial',
        }),
      ],
    }),
  );

  return children;
}

/**
 * Generate and download a Word document with collection letters
 * for a list of clients assigned to this gestor.
 */
export async function downloadLetters(clients, seccion, gestorName = '') {
  if (!clients || clients.length === 0) {
    throw new Error('No hay clientes para generar cartas');
  }

  const sections = [];

  clients.forEach((client, idx) => {
    const children = createLetterSection(client, seccion, gestorName);

    if (idx < clients.length - 1) {
      children.push(new Paragraph({
        children: [new PageBreak()],
      }));
    }

    if (idx === 0) {
      sections.push({
        properties: {
          page: {
            margin: { top: 1134, bottom: 1134, left: 1418, right: 1418 },
          },
        },
        children,
      });
    } else {
      sections[0].children.push(...children);
    }
  });

  const doc = new Document({ sections });
  const blob = await Packer.toBlob(doc);

  const safeName = gestorName
    ? gestorName.replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]/g, '').replace(/\s+/g, '_')
    : seccion;
  saveAs(blob, `Cartas_Cobranza_Seccion_${seccion}_${safeName}.docx`);

  return clients.length;
}

/**
 * Generate a single letter for one client.
 */
export async function downloadSingleLetter(client, seccion, gestorName = '') {
  const children = createLetterSection(client, seccion, gestorName);

  const doc = new Document({
    sections: [{
      properties: {
        page: {
          margin: { top: 1134, bottom: 1134, left: 1418, right: 1418 },
        },
      },
      children,
    }],
  });

  const blob = await Packer.toBlob(doc);
  const nombre = (client.nombre_completo || client.codigo_cliente || 'cliente').replace(/\s+/g, '_');
  saveAs(blob, `Carta_${nombre}.docx`);
}
