/**
 * GPS Background Tracking Service for gestor-app (web).
 *
 * Strategy — "Smart continuous tracking" (FREE):
 *   1. Uses navigator.geolocation.watchPosition() — free browser API
 *   2. Filters by distance: only records if moved > 30m from last point
 *   3. Heartbeat: records at least once every 2 minutes (even if stationary)
 *   4. Batches writes to Firestore every 60 seconds to minimize write count
 *   5. Always keeps a "last known position" summary doc updated
 *
 * Firestore cost estimate:
 *   - ~100 points/hr moving + 30 heartbeats/hr stationary
 *   - 1 summary update per batch (every 60s) = ~480/8hr
 *   - Total: ~1,300 writes/gestor/day → well within free tier (20K/day)
 *
 * Open source tech used:
 *   - Web Geolocation API (W3C standard, all browsers)
 *   - Haversine formula for distance calculation
 */

import { doc, collection, addDoc, setDoc, serverTimestamp, writeBatch } from 'firebase/firestore';
import { db, auth } from './firebase';

// ── Configuration ──
const MIN_DISTANCE_METERS = 30;     // Minimum distance to record a new point
const HEARTBEAT_MS = 2 * 60 * 1000; // Record at least every 2 minutes
const BATCH_INTERVAL_MS = 60 * 1000; // Flush to Firestore every 60 seconds
const MAX_BUFFER_SIZE = 50;          // Force flush if buffer gets too large

class GpsTrackingService {
  constructor() {
    this._watchId = null;
    this._lastRecordedLat = null;
    this._lastRecordedLng = null;
    this._lastRecordedTime = 0;
    this._buffer = [];           // Points waiting to be written
    this._batchTimer = null;
    this._currentPosition = null; // Always the latest position
    this._seccion = '';
    this._gestorName = '';
    this._running = false;
    this._error = null;
  }

  /** Start continuous GPS tracking */
  start({ seccion = '', gestorName = '' } = {}) {
    if (this._running) return;
    if (!navigator.geolocation) {
      this._error = 'Geolocation not supported';
      console.warn('[GPS Tracking] Geolocation not supported');
      return;
    }

    this._seccion = seccion;
    this._gestorName = gestorName;
    this._running = true;
    this._error = null;

    console.info('[GPS Tracking] Starting continuous tracking...');

    // Start watching position
    this._watchId = navigator.geolocation.watchPosition(
      (position) => this._onPosition(position),
      (err) => this._onError(err),
      {
        enableHighAccuracy: true,
        maximumAge: 10000,     // Accept cached positions up to 10s old
        timeout: 30000,
      }
    );

    // Start the batch write timer
    this._batchTimer = setInterval(() => this._flushBuffer(), BATCH_INTERVAL_MS);
  }

  /** Stop tracking and flush remaining data */
  stop() {
    if (!this._running) return;
    this._running = false;

    if (this._watchId !== null) {
      navigator.geolocation.clearWatch(this._watchId);
      this._watchId = null;
    }

    if (this._batchTimer) {
      clearInterval(this._batchTimer);
      this._batchTimer = null;
    }

    // Flush any remaining points
    this._flushBuffer();

    console.info('[GPS Tracking] Stopped.');
  }

  /** Get current state */
  get isRunning() { return this._running; }
  get currentPosition() { return this._currentPosition; }
  get error() { return this._error; }
  get bufferSize() { return this._buffer.length; }

  // ── Internal ──

  _onPosition(position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    const accuracy = position.coords.accuracy;
    const now = Date.now();

    this._currentPosition = { lat, lng, accuracy, timestamp: now };

    // Filter: skip if too close to last recorded point AND heartbeat not due
    if (this._lastRecordedLat !== null) {
      const dist = haversineMeters(this._lastRecordedLat, this._lastRecordedLng, lat, lng);
      const timeSinceLastRecord = now - this._lastRecordedTime;

      if (dist < MIN_DISTANCE_METERS && timeSinceLastRecord < HEARTBEAT_MS) {
        return; // Skip — hasn't moved enough and heartbeat not yet due
      }
    }

    // Record this point to the buffer
    this._buffer.push({
      lat,
      lng,
      accuracy: accuracy || 0,
      fecha: new Date(now).toISOString(),
      tipo: 'auto',     // auto tracking (vs 'visita' which is manual)
      seccion: this._seccion,
    });

    this._lastRecordedLat = lat;
    this._lastRecordedLng = lng;
    this._lastRecordedTime = now;

    // Force flush if buffer is getting large
    if (this._buffer.length >= MAX_BUFFER_SIZE) {
      this._flushBuffer();
    }
  }

  _onError(err) {
    console.warn('[GPS Tracking] Position error:', err.message);
    this._error = err.message;
  }

  async _flushBuffer() {
    const uid = auth.currentUser?.uid;
    if (!uid || this._buffer.length === 0) return;

    // Take the current buffer and reset it
    const points = [...this._buffer];
    this._buffer = [];

    try {
      const trackRef = doc(db, 'ubicaciones_gestores', uid);
      const puntosRef = collection(trackRef, 'puntos');

      // Use batched writes: 1 summary update + N point creates
      const batch = writeBatch(db);

      for (const p of points) {
        const newDoc = doc(puntosRef);
        batch.set(newDoc, {
          ...p,
          timestamp: serverTimestamp(),
          cliente_id: '',
          cliente_nombre: '',
          estado: '',
        });
      }

      // Update summary doc with latest known position
      const latest = points[points.length - 1];
      batch.set(trackRef, {
        ultima_lat: latest.lat,
        ultima_lng: latest.lng,
        ultima_accuracy: latest.accuracy,
        ultimo_timestamp: serverTimestamp(),
        ultimo_cliente: '',
        ultimo_estado: 'tracking',
        seccion: this._seccion,
        gestor_nombre: this._gestorName,
      }, { merge: true });

      await batch.commit();
      console.debug(`[GPS Tracking] Flushed ${points.length} points to Firestore`);
    } catch (err) {
      // Put points back in buffer on failure (will retry next flush)
      console.warn('[GPS Tracking] Flush failed, re-queuing points:', err);
      this._buffer = [...points, ...this._buffer];
    }
  }
}

// ── Haversine distance in meters ──
function haversineMeters(lat1, lon1, lat2, lon2) {
  const R = 6371000; // meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
    Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Singleton
export const gpsTracking = new GpsTrackingService();
