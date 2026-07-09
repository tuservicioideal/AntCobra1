import { useState, useEffect, useCallback, useMemo } from 'react';
import { getRoutesForGestor, getRoutesByDate, deleteRoute, updateRouteClientStatus } from '../services/routeService';
import { MapContainer, TileLayer, Marker, Polyline, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  ArrowLeft, Route, Calendar, Users, MapPin, CheckCircle2, Clock,
  Trash2, Loader2, RefreshCw, ChevronDown, ChevronUp, DollarSign,
  TrendingUp, Eye
} from 'lucide-react';

const STATUS_LABELS = {
  pendiente: 'Pendiente',
  visitado_habido: 'Habido',
  visitado_no_habido: 'No Habido',
  fallecido_inubicable: 'Inubicable',
  suplantacion: 'Suplantación',
  pago_no_registrado: 'Pago NR',
};

const STATUS_COLORS = {
  pendiente: 'bg-slate-100 text-slate-700',
  visitado_habido: 'bg-emerald-100 text-emerald-700',
  visitado_no_habido: 'bg-amber-100 text-amber-700',
  fallecido_inubicable: 'bg-red-100 text-red-700',
  suplantacion: 'bg-rose-100 text-rose-700',
  pago_no_registrado: 'bg-blue-100 text-blue-700',
};

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

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

function orderByNearest(clients, userPos) {
  if (clients.length === 0) return [];
  const pending = [...clients];
  const ordered = [];
  let current = userPos || [pending[0].lat, pending[0].lng];

  while (pending.length > 0) {
    let bestIndex = 0;
    let bestDist = Number.POSITIVE_INFINITY;
    pending.forEach((c, idx) => {
      const d = haversineKm(current[0], current[1], c.lat, c.lng);
      if (d < bestDist) {
        bestDist = d;
        bestIndex = idx;
      }
    });
    const next = pending.splice(bestIndex, 1)[0];
    ordered.push({ ...next, nearest_km: bestDist });
    current = [next.lat, next.lng];
  }
  return ordered;
}

export default function RoutePlanPage({ user, userData, onBack, isAdmin }) {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRoute, setExpandedRoute] = useState(null);
  const [dateFilter, setDateFilter] = useState('');
  const [deleting, setDeleting] = useState(null);
  const [userPos, setUserPos] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserPos([pos.coords.latitude, pos.coords.longitude]),
      () => setUserPos(null),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, []);

  const loadRoutes = useCallback(async () => {
    setLoading(true);
    try {
      let data;
      if (isAdmin && dateFilter) {
        // Admin: view all gestors' routes for a date
        data = await getRoutesByDate(dateFilter);
      } else if (isAdmin) {
        // Admin without date: show today's routes
        const today = new Date().toISOString().slice(0, 10);
        data = await getRoutesByDate(today);
        setDateFilter(today);
      } else {
        // Gestor: only own routes
        data = await getRoutesForGestor(user.uid);
      }
      data.sort((a, b) => (b.fecha || '').localeCompare(a.fecha || ''));
      setRoutes(data);
    } catch (err) {
      console.error('Error loading routes:', err);
    } finally {
      setLoading(false);
    }
  }, [user?.uid, isAdmin, dateFilter]);

  useEffect(() => { loadRoutes(); }, [loadRoutes]);

  const handleDelete = async (route) => {
    if (!confirm(`¿Eliminar la ruta del ${route.fecha}?`)) return;
    setDeleting(route.id);
    try {
      await deleteRoute(route.fecha, route.gestor_uid);
      setRoutes(prev => prev.filter(r => r.id !== route.id));
    } catch (err) {
      console.error('Error deleting route:', err);
    } finally {
      setDeleting(null);
    }
  };

  // ── Summary stats ──
  const summary = useMemo(() => {
    const totalRoutes = routes.length;
    const totalClients = routes.reduce((s, r) => s + (r.total || 0), 0);
    const totalCompleted = routes.reduce((s, r) => s + (r.completados || 0), 0);
    const totalDeuda = routes.reduce((s, r) =>
      s + (r.clientes || []).reduce((ds, c) => ds + (c.importe_deuda || 0), 0)
    , 0);
    return { totalRoutes, totalClients, totalCompleted, totalDeuda };
  }, [routes]);

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
              <Route size={18} />
            </div>
            <div>
              <h1 className="app-topbar-title">Planificación de Rutas</h1>
              <p className="app-topbar-subtitle">
                {summary.totalRoutes} rutas · {summary.totalClients} clientes asignados
              </p>
            </div>
          </div>
          <button onClick={loadRoutes}
            className={`p-2.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all border border-slate-200
                      ${loading ? 'animate-spin' : ''}`}>
            <RefreshCw size={17} />
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-4 space-y-4">
        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-4">
          {isAdmin && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex-1">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5 mb-2">
                <Calendar size={14} /> Filtrar por fecha
              </label>
              <input
                type="date"
                value={dateFilter}
                onChange={e => setDateFilter(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2
                         focus:ring-emerald-500 focus:border-emerald-500 outline-none"
              />
            </div>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1">
            <SummaryCard icon={<Route size={16} />} label="Rutas" value={summary.totalRoutes} color="emerald" />
            <SummaryCard icon={<Users size={16} />} label="Clientes" value={summary.totalClients} color="indigo" />
            <SummaryCard icon={<CheckCircle2 size={16} />} label="Completados" value={summary.totalCompleted} color="green" />
            <SummaryCard
              icon={<DollarSign size={16} />}
              label="Deuda"
              value={`S/ ${summary.totalDeuda.toLocaleString('es-PE', { maximumFractionDigits: 0 })}`}
              color="rose"
              small
            />
          </div>
        </div>

        {/* Route list */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={28} className="animate-spin text-emerald-500" />
          </div>
        ) : routes.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
            <Route size={40} className="text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 font-semibold">Sin rutas planificadas</p>
            <p className="text-sm text-gray-400 mt-1">
              Usa el Mapa de Clientes para seleccionar y guardar rutas.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {routes.map(route => {
              const isExpanded = expandedRoute === route.id;
              const pct = route.total > 0 ? Math.round((route.completados / route.total) * 100) : 0;
              const deudaRoute = (route.clientes || []).reduce((s, c) => s + (c.importe_deuda || 0), 0);
              const routeClientsGeo = (route.clientes || [])
                .filter(c => Number(c.lat) && Number(c.lng))
                .map(c => ({
                  ...c,
                  lat: Number(c.lat),
                  lng: Number(c.lng),
                }));
              const orderedRoute = orderByNearest(routeClientsGeo, userPos);
              const routePolyline = [
                ...(userPos ? [userPos] : []),
                ...orderedRoute.map(c => [c.lat, c.lng]),
              ];

              return (
                <div key={route.id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                  {/* Route header */}
                  <div
                    className="p-4 cursor-pointer hover:bg-slate-50 transition-all"
                    onClick={() => setExpandedRoute(isExpanded ? null : route.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700
                                      flex items-center justify-center shrink-0">
                          <Calendar size={18} />
                        </div>
                        <div>
                          <p className="font-bold text-gray-900">
                            {new Date(route.fecha + 'T12:00:00').toLocaleDateString('es-PE', {
                              weekday: 'long', day: 'numeric', month: 'long'
                            })}
                          </p>
                          {isAdmin && (
                            <p className="text-xs text-gray-500">{route.gestor_nombre}</p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p className="text-sm font-bold text-gray-900">
                            {route.completados}/{route.total}
                          </p>
                          <p className="text-xs text-gray-500">{pct}% completado</p>
                        </div>

                        <button
                          onClick={(e) => { e.stopPropagation(); handleDelete(route); }}
                          disabled={deleting === route.id}
                          className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                        >
                          {deleting === route.id
                            ? <Loader2 size={16} className="animate-spin" />
                            : <Trash2 size={16} />
                          }
                        </button>

                        {isExpanded ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div className="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-green-500 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>

                  {/* Expanded: client list */}
                  {isExpanded && (
                    <div className="border-t border-slate-100">
                      {routeClientsGeo.length > 0 && (
                        <div className="px-4 py-3 border-b border-slate-100 bg-white">
                          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Mapa de ruta sugerida</p>
                          <div className="h-64 rounded-lg overflow-hidden border border-slate-200">
                            <MapContainer
                              center={routePolyline[0] || [routeClientsGeo[0].lat, routeClientsGeo[0].lng]}
                              zoom={13}
                              style={{ width: '100%', height: '100%' }}
                            >
                              <TileLayer
                                attribution='&copy; OpenStreetMap'
                                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                              />
                              {routePolyline.length > 1 && (
                                <Polyline positions={routePolyline} pathOptions={{ color: '#2563EB', weight: 4 }} />
                              )}
                              {orderedRoute.map((c, idx) => (
                                <Marker key={`${c.codigo_cliente || idx}-${idx}`} position={[c.lat, c.lng]}>
                                  <Popup>
                                    <div className="text-xs">
                                      <p className="font-semibold">{idx + 1}. {c.nombre || c.codigo_cliente}</p>
                                      <p>Distancia aprox.: {Number(c.nearest_km || 0).toFixed(2)} km</p>
                                    </div>
                                  </Popup>
                                </Marker>
                              ))}
                            </MapContainer>
                          </div>
                          <div className="mt-2 flex items-center justify-between text-xs">
                            <p className="text-gray-500">
                              Ordenado por cercanía desde tu ubicación actual (aproximado).
                            </p>
                            {orderedRoute[0] && (
                              <a
                                href={`https://www.google.com/maps/dir/?api=1&destination=${orderedRoute[0].lat},${orderedRoute[0].lng}&travelmode=driving`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-emerald-700 font-semibold"
                              >
                                Ir al siguiente
                              </a>
                            )}
                          </div>
                        </div>
                      )}
                      <div className="px-4 py-2 bg-slate-50/60 flex items-center justify-between">
                        <span className="text-xs font-semibold text-gray-500 uppercase">Clientes en ruta</span>
                        <span className="text-xs text-gray-500">
                          Deuda: S/ {deudaRoute.toLocaleString('es-PE', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                      <div className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
                        {(orderedRoute.length > 0 ? orderedRoute : (route.clientes || [])).map((c, idx) => (
                          <div key={c.codigo_cliente || idx}
                            className="px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-all">
                            <div className="flex items-center gap-3 min-w-0">
                              <span className="text-xs font-bold text-gray-400 w-6">{idx + 1}</span>
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-gray-900 truncate">
                                  {c.nombre || c.codigo_cliente}
                                </p>
                                {c.seccion_key && (
                                  <p className="text-xs text-gray-400">Sección {c.seccion_key}</p>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-3 shrink-0">
                              <span className="text-xs font-medium text-gray-600">
                                S/ {(c.importe_deuda || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}
                              </span>
                              <span className={`text-xs px-2 py-0.5 rounded-md font-medium 
                                ${STATUS_COLORS[c.estado] || 'bg-slate-100 text-slate-700'}`}>
                                {STATUS_LABELS[c.estado] || c.estado || 'Pendiente'}
                              </span>
                              {c.lat && c.lng && (
                                <MapPin size={13} className="text-emerald-500" />
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ icon, label, value, color, small }) {
  const colors = {
    emerald: 'bg-emerald-50 text-emerald-700',
    indigo: 'bg-indigo-50 text-indigo-700',
    green: 'bg-green-50 text-green-700',
    rose: 'bg-rose-50 text-rose-700',
  };
  return (
    <div className={`rounded-xl p-3 ${colors[color] || colors.indigo}`}>
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</span>
      </div>
      <p className={`font-bold ${small ? 'text-sm' : 'text-lg'}`}>{value}</p>
    </div>
  );
}
