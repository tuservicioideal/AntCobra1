import { useState, useEffect, useMemo } from 'react';
import { collection, getDocs, query, orderBy, doc, getDoc } from 'firebase/firestore';
import { db } from '../services/firebase';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  ArrowLeft, MapPin, Users, Calendar, Route, RefreshCw, ChevronDown, ChevronUp,
  Clock, Navigation, Eye, EyeOff, Footprints
} from 'lucide-react';

// ── Leaflet icon fix (default marker icons broken in bundlers) ──
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// ── Custom colored marker icons ──
function createColorIcon(color) {
  return new L.DivIcon({
    html: `<div style="
      background:${color}; width:28px; height:28px; border-radius:50%;
      border:3px solid white; box-shadow:0 2px 6px rgba(0,0,0,.35);
      display:flex; align-items:center; justify-content:center;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
      </svg>
    </div>`,
    className: '',
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -28],
  });
}

const SECTION_COLORS = {
  A: '#4F46E5', B: '#0D9488', C: '#D97706', D: '#DC2626',
  E: '#7C3AED', F: '#059669', G: '#DB2777', H: '#2563EB',
  I: '#CA8A04', J: '#6366F1',
};

function getSectionColor(sec) {
  return SECTION_COLORS[sec?.toUpperCase()] || '#6B7280';
}

// ── Haversine distance (km) ──
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
    Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ── Compute total km from ordered points ──
function computeTotalKm(points) {
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    total += haversineKm(points[i - 1].lat, points[i - 1].lng, points[i].lat, points[i].lng);
  }
  return total;
}

// ── Status labels ──
const STATUS_LABELS = {
  visitado_habido: 'Visitado (Habido)',
  visitado_no_habido: 'Visitado (No Habido)',
  fallecido_inubicable: 'Fallecido / Inubicable',
  suplantacion: 'Suplantación',
  pago_no_registrado: 'Pago no registrado',
  pendiente: 'Pendiente',
};

export default function TrackingPage({ onBack }) {
  const [gestores, setGestores] = useState([]);
  const [trackingData, setTrackingData] = useState({});
  const [selectedGestor, setSelectedGestor] = useState(null);
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [expandedGestor, setExpandedGestor] = useState(null);

  // ── Load gestors and their tracking data ──
  const loadData = async () => {
    setLoading(true);
    try {
      // 1. Get all users to know gestor names
      const usersSnap = await getDocs(collection(db, 'usuarios'));
      const usersMap = {};
      const gestorList = [];
      usersSnap.forEach(d => {
        const u = { id: d.id, ...d.data() };
        usersMap[d.id] = u;
        // Only include active users with sections
        if (u.activo !== false && u.seccion) {
          gestorList.push(u);
        }
      });

      // De-duplicate by email
      const byEmail = {};
      for (const g of gestorList) {
        const email = (g.email || '').toLowerCase();
        if (!email) continue;
        if (!byEmail[email] || (g.uid && !byEmail[email].uid)) {
          byEmail[email] = g;
        }
      }
      const uniqueGestores = Object.values(byEmail);
      setGestores(uniqueGestores);

      // 2. Get tracking summary docs (last known position)
      const trackSnap = await getDocs(collection(db, 'ubicaciones_gestores'));
      const tracking = {};
      trackSnap.forEach(d => {
        tracking[d.id] = { id: d.id, ...d.data(), puntos: [] };
      });

      // 3. For each tracked gestor, get their points
      for (const docSnap of trackSnap.docs) {
        const uid = docSnap.id;
        try {
          const puntosSnap = await getDocs(
            query(collection(db, 'ubicaciones_gestores', uid, 'puntos'), orderBy('fecha', 'asc'))
          );
          const puntos = [];
          puntosSnap.forEach(p => {
            const data = p.data();
            if (data.lat && data.lng) {
              puntos.push({ id: p.id, ...data });
            }
          });
          if (tracking[uid]) {
            tracking[uid].puntos = puntos;
          } else {
            tracking[uid] = { id: uid, puntos };
          }
          // Link gestor name if we have it
          if (usersMap[uid]) {
            tracking[uid].nombre = usersMap[uid].nombre;
            tracking[uid].seccion = usersMap[uid].seccion;
            tracking[uid].email = usersMap[uid].email;
          }
        } catch (err) {
          console.warn(`Could not load points for ${uid}:`, err);
        }
      }

      setTrackingData(tracking);
    } catch (err) {
      console.error('Error loading tracking data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  // ── Filter points by selected date ──
  const getFilteredPoints = (uid) => {
    const data = trackingData[uid];
    if (!data?.puntos?.length) return [];
    return data.puntos.filter(p => {
      const fecha = p.fecha || '';
      return fecha.startsWith(selectedDate);
    });
  };

  // ── Map markers for all gestors with data ──
  const mapData = useMemo(() => {
    const markers = [];
    const routes = [];

    const gestorsToShow = selectedGestor
      ? [selectedGestor]
      : Object.keys(trackingData);

    for (const uid of gestorsToShow) {
      const data = trackingData[uid];
      if (!data) continue;

      const points = getFilteredPoints(uid);
      const sec = data.seccion || '';
      const color = getSectionColor(sec);
      const nombre = data.nombre || data.email || uid.slice(0, 8);

      // Route polyline
      if (points.length > 1) {
        routes.push({
          uid,
          positions: points.map(p => [p.lat, p.lng]),
          color,
          nombre,
          km: computeTotalKm(points),
        });
      }

      // Individual visit markers
      points.forEach((p, idx) => {
        markers.push({
          uid,
          position: [p.lat, p.lng],
          color,
          nombre,
          sec,
          punto: p,
          isLast: idx === points.length - 1,
        });
      });
    }

    return { markers, routes };
  }, [trackingData, selectedGestor, selectedDate]);

  // ── Km summary per gestor for selected date ──
  const kmSummary = useMemo(() => {
    const summary = {};
    for (const uid of Object.keys(trackingData)) {
      const points = getFilteredPoints(uid);
      summary[uid] = {
        km: computeTotalKm(points),
        visits: points.length,
        points,
      };
    }
    return summary;
  }, [trackingData, selectedDate]);

  // ── Map center ──
  const mapCenter = useMemo(() => {
    if (mapData.markers.length > 0) {
      const lats = mapData.markers.map(m => m.position[0]);
      const lngs = mapData.markers.map(m => m.position[1]);
      return [
        (Math.min(...lats) + Math.max(...lats)) / 2,
        (Math.min(...lngs) + Math.max(...lngs)) / 2,
      ];
    }
    return [-12.0464, -77.0428]; // Lima, Peru default
  }, [mapData.markers]);

  // ── Available dates from all points ──
  const availableDates = useMemo(() => {
    const dates = new Set();
    for (const data of Object.values(trackingData)) {
      for (const p of data.puntos || []) {
        if (p.fecha) dates.add(p.fecha.slice(0, 10));
      }
    }
    return [...dates].sort().reverse();
  }, [trackingData]);

  return (
    <div className="app-page">
      {/* Header */}
      <header className="app-topbar">
        <div className="app-topbar-inner">
          <div className="flex items-center gap-3">
            {onBack && (
              <button onClick={onBack} className="app-back-btn">
                <ArrowLeft size={18} />
              </button>
            )}
            <div className="app-icon-chip">
              <Navigation size={18} />
            </div>
            <div>
              <h1 className="app-topbar-title">Rastreo de Gestores</h1>
              <p className="app-topbar-subtitle">
                {Object.keys(trackingData).length} gestores con datos GPS
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadData}
              className={`p-2.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all border border-slate-200
                        ${loading ? 'animate-spin' : ''}`}>
              <RefreshCw size={17} />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-4 flex flex-col lg:flex-row gap-4">
        {/* Sidebar: Controls + Gestor list */}
        <div className="w-full lg:w-80 shrink-0 space-y-4">
          {/* Date filter */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5 mb-2">
              <Calendar size={14} /> Fecha
            </label>
            <input
              type="date"
              value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2
                       focus:ring-teal-500 focus:border-teal-500 outline-none"
            />
            {availableDates.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {availableDates.slice(0, 5).map(d => (
                  <button key={d} onClick={() => setSelectedDate(d)}
                    className={`text-xs px-2 py-1 rounded-md font-medium transition-all
                      ${d === selectedDate
                        ? 'bg-teal-100 text-teal-700 border border-teal-200'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-transparent'
                      }`}>
                    {d.slice(5)}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* View options */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Opciones
              </span>
              <button onClick={() => setShowRoutes(!showRoutes)}
                className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg font-medium transition-all
                  ${showRoutes
                    ? 'bg-teal-50 text-teal-700 border border-teal-200'
                    : 'bg-slate-100 text-slate-500 border border-slate-200'
                  }`}>
                {showRoutes ? <Eye size={13} /> : <EyeOff size={13} />}
                Rutas
              </button>
            </div>
            <button
              onClick={() => setSelectedGestor(null)}
              className={`mt-2 w-full text-xs px-3 py-2 rounded-lg font-medium transition-all
                ${!selectedGestor
                  ? 'bg-teal-100 text-teal-700 border border-teal-200'
                  : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}>
              <Users size={13} className="inline mr-1" /> Ver todos los gestores
            </button>
          </div>

          {/* Gestor list with km */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
                <Footprints size={14} /> Historial de Recorridos
              </h3>
            </div>
            <div className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
              {loading ? (
                <div className="p-6 text-center text-sm text-gray-400">
                  <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
                  Cargando datos...
                </div>
              ) : Object.keys(trackingData).length === 0 ? (
                <div className="p-6 text-center text-sm text-gray-400">
                  <MapPin size={20} className="mx-auto mb-2 opacity-50" />
                  Sin datos de ubicación aún
                </div>
              ) : (
                Object.entries(trackingData).map(([uid, data]) => {
                  const summary = kmSummary[uid] || { km: 0, visits: 0 };
                  const sec = data.seccion || '?';
                  const color = getSectionColor(sec);
                  const isSelected = selectedGestor === uid;
                  const isExpanded = expandedGestor === uid;

                  return (
                    <div key={uid}>
                      <div
                        className={`p-3 cursor-pointer hover:bg-slate-50 transition-all
                          ${isSelected ? 'bg-teal-50 border-l-4 border-teal-500' : 'border-l-4 border-transparent'}`}
                        onClick={() => {
                          setSelectedGestor(isSelected ? null : uid);
                        }}>
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                               style={{ background: color }}>
                            {sec}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-gray-800 truncate">
                              {data.nombre || data.email || uid.slice(0, 12)}
                            </p>
                            <div className="flex items-center gap-3 text-xs text-gray-500">
                              <span className="flex items-center gap-1">
                                <Route size={11} />
                                {summary.km.toFixed(2)} km
                              </span>
                              <span className="flex items-center gap-1">
                                <MapPin size={11} />
                                {summary.visits} puntos
                              </span>
                            </div>
                          </div>
                          <button onClick={(e) => { e.stopPropagation(); setExpandedGestor(isExpanded ? null : uid); }}
                            className="p-1 hover:bg-slate-200 rounded-lg transition-all">
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>
                        </div>
                      </div>

                      {/* Expanded: point-by-point history */}
                      {isExpanded && (
                        <div className="bg-slate-50 px-4 py-2 space-y-1 max-h-48 overflow-y-auto border-t border-slate-100">
                          {(kmSummary[uid]?.points || []).length === 0 ? (
                            <p className="text-xs text-gray-400 py-2">Sin puntos para esta fecha</p>
                          ) : (
                            kmSummary[uid].points.map((p, idx) => (
                              <div key={p.id || idx} className="flex items-center gap-2 text-xs py-1">
                                <div className="w-5 h-5 rounded-full flex items-center justify-center text-white font-bold shrink-0"
                                     style={{ background: color, fontSize: '9px' }}>
                                  {idx + 1}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <span className="font-medium text-gray-700">
                                    {p.cliente_nombre || 'Punto ' + (idx + 1)}
                                  </span>
                                  <span className="ml-1.5 text-gray-400">
                                    {STATUS_LABELS[p.estado] || p.estado || ''}
                                  </span>
                                </div>
                                <span className="text-gray-400 shrink-0 flex items-center gap-0.5">
                                  <Clock size={10} />
                                  {p.fecha ? new Date(p.fecha).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }) : '—'}
                                </span>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Km summary table */}
          {Object.keys(trackingData).length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Route size={14} /> Resumen Km — {selectedDate}
              </h3>
              <div className="space-y-2">
                {Object.entries(kmSummary)
                  .sort(([, a], [, b]) => b.km - a.km)
                  .map(([uid, s]) => {
                    const data = trackingData[uid];
                    const sec = data?.seccion || '?';
                    return (
                      <div key={uid} className="flex items-center gap-2 text-sm">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold"
                             style={{ background: getSectionColor(sec) }}>
                          {sec}
                        </div>
                        <span className="flex-1 truncate text-gray-700 font-medium text-xs">
                          {data?.nombre || uid.slice(0, 10)}
                        </span>
                        <span className="text-xs font-bold text-gray-800">
                          {s.km.toFixed(2)} km
                        </span>
                        <span className="text-xs text-gray-400">
                          ({s.visits} pts)
                        </span>
                      </div>
                    );
                  })}
              </div>
              <div className="mt-3 pt-3 border-t border-slate-100 flex justify-between text-sm font-bold">
                <span className="text-gray-600">Total</span>
                <span className="text-teal-700">
                  {Object.values(kmSummary).reduce((acc, s) => acc + s.km, 0).toFixed(2)} km
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Map */}
        <div className="flex-1 min-h-[500px] lg:min-h-0 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center text-gray-400">
              <div className="text-center">
                <RefreshCw size={28} className="animate-spin mx-auto mb-3" />
                <p className="text-sm">Cargando mapa...</p>
              </div>
            </div>
          ) : (
            <MapContainer
              key={`${mapCenter[0]}-${mapCenter[1]}`}
              center={mapCenter}
              zoom={13}
              style={{ height: '100%', minHeight: '500px', width: '100%' }}
              zoomControl={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {/* Route polylines */}
              {showRoutes && mapData.routes.map(route => (
                <Polyline
                  key={route.uid}
                  positions={route.positions}
                  pathOptions={{
                    color: route.color,
                    weight: 3,
                    opacity: 0.7,
                    dashArray: '8, 6',
                  }}
                />
              ))}

              {/* Visit point markers */}
              {mapData.markers.map((m, idx) => (
                m.isLast ? (
                  <Marker
                    key={`${m.uid}-${idx}`}
                    position={m.position}
                    icon={createColorIcon(m.color)}
                  >
                    <Popup>
                      <div className="text-sm min-w-[180px]">
                        <p className="font-bold">{m.nombre}</p>
                        <p className="text-gray-500">Sección {m.sec}</p>
                        <hr className="my-1" />
                        <p><strong>Cliente:</strong> {m.punto.cliente_nombre || '—'}</p>
                        <p><strong>Estado:</strong> {STATUS_LABELS[m.punto.estado] || m.punto.estado}</p>
                        <p><strong>Hora:</strong> {m.punto.fecha
                          ? new Date(m.punto.fecha).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
                          : '—'
                        }</p>
                        <p className="text-[10px] text-gray-400 mt-1">
                          📍 Última posición conocida
                        </p>
                      </div>
                    </Popup>
                  </Marker>
                ) : (
                  <CircleMarker
                    key={`${m.uid}-${idx}`}
                    center={m.position}
                    radius={6}
                    pathOptions={{
                      color: m.color,
                      fillColor: m.color,
                      fillOpacity: 0.7,
                      weight: 2,
                    }}
                  >
                    <Popup>
                      <div className="text-sm min-w-[160px]">
                        <p className="font-bold">{m.nombre}</p>
                        <p><strong>Cliente:</strong> {m.punto.cliente_nombre || '—'}</p>
                        <p><strong>Estado:</strong> {STATUS_LABELS[m.punto.estado] || m.punto.estado}</p>
                        <p><strong>Hora:</strong> {m.punto.fecha
                          ? new Date(m.punto.fecha).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
                          : '—'
                        }</p>
                      </div>
                    </Popup>
                  </CircleMarker>
                )
              ))}
            </MapContainer>
          )}
        </div>
      </div>
    </div>
  );
}
