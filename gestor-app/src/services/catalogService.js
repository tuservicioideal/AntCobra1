/**
 * Territorial catalog service — reads the region/zona/section hierarchy
 * from the `estructura_territorial/catalogo` Firestore document.
 */

import { doc, getDoc } from 'firebase/firestore';
import { db } from './firebase';

/**
 * Fetch the territorial catalog.
 * @returns {Promise<Object>} The `regiones` map, e.g.:
 *   { "01": { zonas: { "1211": { secciones: ["H","C"] } } } }
 *   Returns empty object if catalog doesn't exist.
 */
export async function getEstructuraTerritorial() {
  try {
    const snap = await getDoc(doc(db, 'estructura_territorial', 'catalogo'));
    if (snap.exists()) {
      return snap.data()?.regiones ?? {};
    }
    return {};
  } catch (err) {
    console.error('getEstructuraTerritorial error:', err);
    return {};
  }
}
