import { toJpeg } from 'html-to-image';
import {
  collection,
  doc,
  getDoc,
  getDocs,
  query,
  serverTimestamp,
  setDoc,
  where,
} from 'firebase/firestore';
import { getDownloadURL, ref, uploadBytes } from 'firebase/storage';
import { auth, db, storage } from './firebase';
import {
  getLetterCss,
  getLetterTemplateHtml,
  mapClientToPlaceholders,
  validatePlaceholders,
} from './letterJpgTemplates';

function resolveTemplateId(client) {
  const numeroCarta = Number(client?.numero_carta || 0);
  if (numeroCarta >= 1 && numeroCarta <= 5) return numeroCarta;
  const tramo = Number(client?.tramo_actual || 1);
  if (tramo <= 1) return 1;
  if (tramo === 2) return 3;
  if (tramo >= 3) return 5;
  return 1;
}

async function getGlobalWatermarkUrl() {
  const docsToTry = [
    doc(db, 'configuracion', 'cartas_jpg'),
    doc(db, 'configuracion', 'marca_agua_cartas'),
  ];
  for (const d of docsToTry) {
    try {
      const snap = await getDoc(d);
      if (!snap.exists()) continue;
      const data = snap.data() || {};
      if (data.watermark_url) return String(data.watermark_url);
      if (data.watermarkUrl) return String(data.watermarkUrl);
    } catch {
      // Ignore missing indexes/offline for this optional config
    }
  }
  return '';
}

function sanitizeName(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/_+/g, '_')
    .slice(0, 80);
}

function buildDomNode(html, css) {
  const root = document.createElement('div');
  root.style.position = 'fixed';
  root.style.left = '-10000px';
  root.style.top = '0';
  root.style.zIndex = '-1';
  root.style.background = '#fff';
  root.innerHTML = `<style>${css}</style>${html}`;
  document.body.appendChild(root);
  return root;
}

async function renderHtmlToJpegBlob({ html, css, quality = 0.96 }) {
  const node = buildDomNode(html, css);
  try {
    const dataUrl = await toJpeg(node, {
      cacheBust: true,
      quality,
      pixelRatio: 2,
      backgroundColor: '#ffffff',
    });
    const res = await fetch(dataUrl);
    return await res.blob();
  } finally {
    node.remove();
  }
}

async function findExistingServerLetter({ campaignId, clientId, templateId }) {
  const cartasRef = collection(db, 'cartas_generadas');
  const lookups = [
    query(
      cartasRef,
      where('campaign_id', '==', campaignId),
      where('cliente_id', '==', String(clientId)),
      where('numero_carta', '==', Number(templateId)),
    ),
  ];
  for (const q of lookups) {
    try {
      const snap = await getDocs(q);
      const rows = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
      const jpgRows = rows.filter((r) => String(r.mime_type || '').startsWith('image/'));
      if (jpgRows.length > 0) {
        jpgRows.sort((a, b) => (b.created_at?.seconds || 0) - (a.created_at?.seconds || 0));
        return jpgRows[0];
      }
    } catch {
      // Tolerate index errors
    }
  }
  return null;
}

export async function generateAndPublishLetterJpg({
  client,
  campaignId = 'cartera_activa',
  gestorName = '',
  gestorPhone = '',
  campaignName = '',
  templateId,
}) {
  const uid = auth.currentUser?.uid;
  if (!uid) throw new Error('No hay sesión activa para generar la carta.');

  const cartaId = Number(templateId || resolveTemplateId(client));
  const clientId = client.codigo_cliente || client.id;
  const seccionKey = client.seccion_key || client.seccion || 'SIN_SECCION';

  const existing = await findExistingServerLetter({
    campaignId,
    clientId,
    templateId: cartaId,
  });
  if (existing) {
    return {
      mode: 'server',
      letter: existing,
    };
  }

  const placeholders = mapClientToPlaceholders({
    client,
    gestorName,
    gestorPhone,
    campaignName,
  });
  const validation = validatePlaceholders(placeholders);
  if (!validation.ok) {
    throw new Error(`Faltan datos del cliente para la carta: ${validation.missing.join(', ')}`);
  }

  const watermarkUrl = await getGlobalWatermarkUrl();
  const html = getLetterTemplateHtml({
    templateId: cartaId,
    placeholders,
    watermarkUrl,
  });
  const css = getLetterCss();
  const jpgBlob = await renderHtmlToJpegBlob({ html, css });

  const safeClient = sanitizeName(placeholders.NOMBRE || clientId || 'cliente');
  const filename = `Carta_${cartaId}_Cli${sanitizeName(clientId)}_${safeClient}.jpg`;
  const storagePath = `cartas_generadas/${campaignId}/${seccionKey}/${uid}/${filename}`;
  const storageRef = ref(storage, storagePath);
  await uploadBytes(storageRef, jpgBlob, { contentType: 'image/jpeg' });
  const downloadUrl = await getDownloadURL(storageRef);

  const docId = `${campaignId}_${cartaId}_${seccionKey}_${uid}_${sanitizeName(clientId)}`;
  const payload = {
    campaign_id: campaignId,
    numero_carta: cartaId,
    cliente_id: String(clientId),
    seccion_key: seccionKey,
    gestor_uid: uid,
    nombre_archivo: filename,
    mime_type: 'image/jpeg',
    tipo: 'jpg',
    storage_path: storagePath,
    download_url: downloadUrl,
    size_bytes: jpgBlob.size || 0,
    estado: 'disponible',
    source_mode: 'client_fallback',
    created_at: serverTimestamp(),
  };
  await setDoc(doc(db, 'cartas_generadas', docId), payload, { merge: true });

  return {
    mode: 'fallback',
    letter: {
      id: docId,
      ...payload,
    },
  };
}
