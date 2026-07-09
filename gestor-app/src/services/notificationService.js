/**
 * Notification Service — Read real-time notifications from Firestore
 * Listens for 'notificaciones' documents targeted at the current user.
 */

import {
  collection, query, where, orderBy, onSnapshot,
  doc, updateDoc, getDocs, limit,
} from 'firebase/firestore';
import { db } from './firebase';

/**
 * Subscribe to real-time notifications for a specific user.
 * @param {string} uid - The user's Firebase UID
 * @param {function} callback - Called with array of notification objects
 * @returns {function} Unsubscribe function
 */
export function subscribeNotifications(uid, callback) {
  if (!uid) return () => {};

  const q = query(
    collection(db, 'notificaciones'),
    where('destinatario_uid', '==', uid),
    orderBy('fecha', 'desc'),
    limit(50),
  );

  return onSnapshot(q, (snapshot) => {
    const notifications = snapshot.docs.map((d) => ({
      id: d.id,
      ...d.data(),
      fecha_str: d.data().fecha?.toDate?.()
        ? d.data().fecha.toDate().toLocaleString('es-PE', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
          })
        : '—',
    }));
    callback(notifications);
  }, (error) => {
    console.error('[NotificationService] Listener error:', error);
    callback([]);
  });
}

/**
 * Mark a notification as read.
 * @param {string} notifId - Document ID
 */
export async function markAsRead(notifId) {
  try {
    await updateDoc(doc(db, 'notificaciones', notifId), { leida: true });
    return true;
  } catch (err) {
    console.error('[NotificationService] Error marking read:', err);
    return false;
  }
}

/**
 * Get unread count (one-time).
 * @param {string} uid
 * @returns {Promise<number>}
 */
export async function getUnreadCount(uid) {
  if (!uid) return 0;
  try {
    const q = query(
      collection(db, 'notificaciones'),
      where('destinatario_uid', '==', uid),
      where('leida', '==', false),
    );
    const snap = await getDocs(q);
    return snap.size;
  } catch {
    return 0;
  }
}
