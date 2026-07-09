import { doc, getDoc } from 'firebase/firestore';
import { db } from './firebase';
import { generateAndPublishLetterJpg } from './letterJpgService';
import { getClientLetters, getLetterUrl } from './documentService';

function resolveTemplateId(client) {
  const numeroCarta = Number(client?.numero_carta || 0);
  if (numeroCarta >= 1 && numeroCarta <= 5) return numeroCarta;
  const tramo = Number(client?.tramo_actual || 1);
  if (tramo <= 1) return 1;
  if (tramo === 2) return 3;
  if (tramo >= 3) return 5;
  return 1;
}

async function ensureLetterUrl({ client, gestorName }) {
  const campaignId = client.campaignId || 'cartera_activa';
  const clientId = client.codigo_cliente || client.id;
  let letters = await getClientLetters({ campaignId, clientId });
  if (!letters.length) {
    const campaignSnap = await getDoc(doc(db, 'campañas', campaignId));
    const campaignName = campaignSnap.exists() ? (campaignSnap.data()?.nombre || '') : '';
    await generateAndPublishLetterJpg({
      client,
      campaignId,
      gestorName: gestorName || '',
      campaignName,
      templateId: resolveTemplateId(client),
    });
    letters = await getClientLetters({ campaignId, clientId });
  }
  if (!letters.length) return null;
  return getLetterUrl(letters[0]);
}

export async function downloadLettersJpgForClients(clients, gestorName = '') {
  let downloaded = 0;
  for (const client of clients) {
    try {
      const url = await ensureLetterUrl({ client, gestorName });
      if (!url) continue;
      const a = document.createElement('a');
      a.href = url;
      const clientName = (client.nombre_completo || client.codigo_cliente || 'cliente')
        .replace(/\s+/g, '_')
        .slice(0, 60);
      a.download = `Carta_${clientName}.jpg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      downloaded += 1;
      await new Promise((r) => setTimeout(r, 220));
    } catch {
      // continue with next client
    }
  }
  return downloaded;
}
