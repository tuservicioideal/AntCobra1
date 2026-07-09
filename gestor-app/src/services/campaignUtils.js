/**
 * Campaign utilities — shared helpers for finding the active campaign.
 *
 * Strategy:
 *  1. Try "cartera_activa" (the canonical, idempotent campaign).
 *  2. If it doesn't exist, fall back to the most recently-created
 *     CAM_YYYYMMDD_HHMMSS campaign (sorted desc by ID).
 */

import { collection, getDocs, doc, getDoc } from 'firebase/firestore';
import { db } from './firebase';

/**
 * Returns the campaign ID to use for loading data.
 * @returns {Promise<string|null>}
 */
export async function getActiveCampaignId() {
  try {
    // 1. Check for the canonical "cartera_activa"
    const activeRef = doc(db, 'campañas', 'cartera_activa');
    const activeSnap = await getDoc(activeRef);
    if (activeSnap.exists()) return 'cartera_activa';

    // 2. Fallback: list all campaigns and pick the latest by ID
    const snap = await getDocs(collection(db, 'campañas'));
    if (snap.empty) return null;

    const ids = snap.docs.map((d) => d.id).sort();
    return ids[ids.length - 1]; // latest by lexicographic order
  } catch (err) {
    console.error('getActiveCampaignId error:', err);
    return null;
  }
}
