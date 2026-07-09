import { collection, getDocs, query, where, doc, getDoc } from 'firebase/firestore';
import { getDownloadURL, ref } from 'firebase/storage';
import { auth, db, storage } from './firebase';

async function getCurrentUserSections() {
  const uid = auth.currentUser?.uid;
  if (!uid) return [];
  const snap = await getDoc(doc(db, 'usuarios', uid));
  if (!snap.exists()) return [];
  const data = snap.data() || {};
  const sections = Array.isArray(data.secciones) ? data.secciones : [];
  if (data.seccion && typeof data.seccion === 'string') {
    sections.push(data.seccion);
  }
  return [...new Set(sections.filter(Boolean))];
}

export async function getClientLetters({ campaignId, clientId }) {
  if (!campaignId || !clientId) return [];
  const uid = auth.currentUser?.uid || '';
  const cartasRef = collection(db, 'cartas_generadas');
  const sections = await getCurrentUserSections();
  const letterQueries = [
    query(cartasRef, where('campaign_id', '==', campaignId), where('cliente_id', '==', String(clientId))),
  ];

  if (uid) {
    letterQueries.push(
      query(
        cartasRef,
        where('campaign_id', '==', campaignId),
        where('cliente_id', '==', String(clientId)),
        where('gestor_uid', '==', uid),
      ),
    );
  }
  for (const section of sections) {
    letterQueries.push(
      query(
        cartasRef,
        where('campaign_id', '==', campaignId),
        where('cliente_id', '==', String(clientId)),
        where('seccion_key', '==', section),
      ),
    );
  }

  const allDocs = [];
  for (const q of letterQueries) {
    try {
      const snap = await getDocs(q);
      allDocs.push(...snap.docs);
    } catch {
      // Tolerate missing composite indexes for fallback queries
    }
  }

  const dedup = new Map();
  allDocs.forEach((d) => dedup.set(d.id, { id: d.id, ...d.data() }));
  return [...dedup.values()]
    .filter((item) => (item.mime_type || '').startsWith('image/'))
    .sort((a, b) => {
      const aTs = a.created_at?.seconds || 0;
      const bTs = b.created_at?.seconds || 0;
      return bTs - aTs;
    });
}

export async function getLetterUrl(letter) {
  if (letter.download_url) return letter.download_url;
  if (!letter.storage_path) throw new Error('No existe ruta de almacenamiento para esta carta.');
  return getDownloadURL(ref(storage, letter.storage_path));
}

