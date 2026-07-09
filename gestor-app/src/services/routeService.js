/**
 * Route Service — CRUD for daily routes (rutas_diarias).
 *
 * Firestore schema:
 *   rutas_diarias/{date}_{gestorUid}
 *     - gestor_uid: string
 *     - gestor_nombre: string
 *     - fecha: string (YYYY-MM-DD)
 *     - clientes: array of { codigo_cliente, nombre, seccion_key, lat, lng, estado, importe_deuda }
 *     - created_at: ISO string
 *     - updated_at: ISO string
 *     - total: number
 *     - completados: number
 */

import {
  doc, setDoc, getDoc, getDocs, collection, query, where, deleteDoc,
} from 'firebase/firestore';
import { db } from './firebase';

const COLLECTION = 'rutas_diarias';

function routeDocId(fecha, gestorUid) {
  return `${fecha}_${gestorUid}`;
}

/**
 * Save or update a daily route.
 */
export async function saveRoute({ gestorUid, gestorNombre, fecha, clientes }) {
  const docId = routeDocId(fecha, gestorUid);
  const completados = clientes.filter(c => c.estado && c.estado !== 'pendiente').length;
  const now = new Date().toISOString();

  const data = {
    gestor_uid: gestorUid,
    gestor_nombre: gestorNombre,
    fecha,
    clientes,
    total: clientes.length,
    completados,
    created_at: now,
    updated_at: now,
  };

  await setDoc(doc(db, COLLECTION, docId), data, { merge: true });
  return docId;
}

/**
 * Get a specific daily route.
 */
export async function getRoute(fecha, gestorUid) {
  const docId = routeDocId(fecha, gestorUid);
  const snap = await getDoc(doc(db, COLLECTION, docId));
  if (!snap.exists()) return null;
  return { id: snap.id, ...snap.data() };
}

/**
 * Get all routes for a gestor (all dates).
 */
export async function getRoutesForGestor(gestorUid) {
  const snap = await getDocs(
    query(collection(db, COLLECTION), where('gestor_uid', '==', gestorUid))
  );
  return snap.docs.map(d => ({ id: d.id, ...d.data() }));
}

/**
 * Get all routes for a specific date (all gestors).
 */
export async function getRoutesByDate(fecha) {
  const snap = await getDocs(
    query(collection(db, COLLECTION), where('fecha', '==', fecha))
  );
  return snap.docs.map(d => ({ id: d.id, ...d.data() }));
}

/**
 * Delete a specific route.
 */
export async function deleteRoute(fecha, gestorUid) {
  const docId = routeDocId(fecha, gestorUid);
  await deleteDoc(doc(db, COLLECTION, docId));
}

/**
 * Update the completion status of a client within a route.
 */
export async function updateRouteClientStatus(fecha, gestorUid, codigoCliente, nuevoEstado) {
  const route = await getRoute(fecha, gestorUid);
  if (!route) return;

  const clientes = route.clientes.map(c =>
    c.codigo_cliente === codigoCliente ? { ...c, estado: nuevoEstado } : c
  );
  const completados = clientes.filter(c => c.estado && c.estado !== 'pendiente').length;

  await setDoc(doc(db, COLLECTION, routeDocId(fecha, gestorUid)), {
    clientes,
    completados,
    updated_at: new Date().toISOString(),
  }, { merge: true });
}
