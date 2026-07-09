/**
 * Nivel catalog service — reads the 4-level management hierarchy
 * from Firestore `configuracion/catalogo_niveles`.
 *
 * The catalog is loaded once and cached for the session.
 */

import { doc, getDoc } from 'firebase/firestore';
import { db } from './firebase';

let _cache = null;

/**
 * Fetch the nivel catalog from Firestore.
 * Returns { version, canales, niveles: [...] } or null.
 */
export async function getCatalogoNiveles() {
  if (_cache) return _cache;
  try {
    const snap = await getDoc(doc(db, 'configuracion', 'catalogo_niveles'));
    if (snap.exists()) {
      _cache = snap.data();
      return _cache;
    }
    return null;
  } catch (err) {
    console.error('getCatalogoNiveles error:', err);
    return null;
  }
}

/**
 * Build cascading option lists filtered by the current selections.
 *
 * @param {Array} niveles  Full niveles array from catalog
 * @param {string} canal   Selected canal (CAM/TEL) — empty = show all
 * @param {string} n1      Selected nivel1 — empty = show all nivel1 options
 * @param {string} n2      Selected nivel2
 * @param {string} n3      Selected nivel3
 * @returns {{ canales, nivel1Opts, nivel2Opts, nivel3Opts, nivel4Opts }}
 */
export function buildCascadingOptions(niveles, canal, n1, n2, n3) {
  if (!niveles || !niveles.length) {
    return { nivel1Opts: [], nivel2Opts: [], nivel3Opts: [], nivel4Opts: [] };
  }

  let filtered = niveles;
  if (canal) filtered = filtered.filter(n => n.canal === canal);

  const nivel1Opts = [...new Set(filtered.map(n => n.nivel1))].sort();

  let f2 = filtered;
  if (n1) f2 = f2.filter(n => n.nivel1 === n1);
  const nivel2Opts = [...new Set(f2.map(n => n.nivel2))].sort();

  let f3 = f2;
  if (n2) f3 = f3.filter(n => n.nivel2 === n2);
  const nivel3Opts = [...new Set(f3.map(n => n.nivel3))].sort();

  let f4 = f3;
  if (n3) f4 = f4.filter(n => n.nivel3 === n3);
  const nivel4Opts = [...new Set(f4.map(n => n.nivel4))].sort();

  return { nivel1Opts, nivel2Opts, nivel3Opts, nivel4Opts };
}
