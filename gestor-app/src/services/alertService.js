/**
 * Alert Service — Write real-time alerts to Firestore
 * Triggered when a gestor reports suplantación or pago_no_registrado.
 * These alerts appear immediately for admin/supervisor users.
 */

import { collection, addDoc, serverTimestamp, query, where, getDocs, doc, updateDoc, onSnapshot, orderBy, limit } from 'firebase/firestore';
import { db } from './firebase';

/**
 * Create a new alert in the `alertas` collection.
 * @param {Object} params
 * @param {'suplantacion'|'pago_no_registrado'} params.tipo
 * @param {Object} params.client - Client data
 * @param {string} params.seccion
 * @param {string} params.gestorEmail
 * @param {string} params.gestorName
 * @param {Object|null} params.gps - { latitude, longitude, accuracy, timestamp }
 * @param {string} params.nota - Gestor note
 * @param {string} params.campaignId
 */
export async function createAlert({
  tipo,
  client,
  seccion,
  gestorEmail,
  gestorName,
  gps,
  nota,
  campaignId = 'cartera_activa',
}) {
  try {
    await addDoc(collection(db, 'alertas'), {
      tipo,
      cliente_codigo: client.codigo_cliente || client.id || '',
      cliente_nombre: client.nombre_completo || '',
      cliente_deuda: parseFloat(client.importe_deuda_asignada || 0),
      seccion: seccion || '',
      gestor_email: gestorEmail || '',
      gestor_nombre: gestorName || '',
      gps: gps ? {
        latitude: gps.latitude,
        longitude: gps.longitude,
        accuracy: gps.accuracy,
        timestamp: gps.timestamp,
      } : null,
      nota: nota || '',
      fecha: serverTimestamp(),
      estado_alerta: 'pendiente',
      campaign_id: campaignId,
    });
    return true;
  } catch (err) {
    console.error('[AlertService] Error creating alert:', err);
    return false;
  }
}

/**
 * Get pending alerts count (for admin badge).
 * @returns {Promise<number>}
 */
export async function getPendingAlertCount() {
  try {
    const q = query(
      collection(db, 'alertas'),
      where('estado_alerta', '==', 'pendiente')
    );
    const snap = await getDocs(q);
    return snap.size;
  } catch (err) {
    console.error('[AlertService] Error counting alerts:', err);
    return 0;
  }
}

/**
 * Subscribe to pending alerts in real-time.
 * @param {Function} callback - Called with array of alert objects
 * @returns {Function} Unsubscribe function
 */
export function subscribePendingAlerts(callback) {
  const q = query(
    collection(db, 'alertas'),
    where('estado_alerta', '==', 'pendiente'),
    orderBy('fecha', 'desc'),
    limit(50)
  );
  return onSnapshot(q, (snap) => {
    const alerts = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    callback(alerts);
  }, (err) => {
    console.error('[AlertService] Subscription error:', err);
    callback([]);
  });
}

/**
 * Mark an alert as reviewed.
 * @param {string} alertId
 */
export async function markAlertReviewed(alertId) {
  try {
    await updateDoc(doc(db, 'alertas', alertId), {
      estado_alerta: 'revisada',
      fecha_revision: serverTimestamp(),
    });
    return true;
  } catch (err) {
    console.error('[AlertService] Error marking alert:', err);
    return false;
  }
}
