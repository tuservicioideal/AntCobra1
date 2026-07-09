import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { collection, getDocs } from 'firebase/firestore';
import { db } from '../services/firebase';
import { getActiveCampaignId } from '../services/campaignUtils';
import { saveRoute, getRoute } from '../services/routeService';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import 'leaflet-draw';
import {
  ArrowLeft, MapPin, Users, Loader2, RefreshCw, CheckCircle2, Circle,
  Hexagon, Save, Trash2, Eye, EyeOff, Filter, Search, Calendar, Route
} from 'lucide-react';

// ── Leaflet icon fix ──
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Workaround for leaflet-draw 1.0.4 bug: `type` is used undeclared in readableArea.
if (L.GeometryUtil?.readableArea) {
  L.GeometryUtil.readableArea = function readableAreaSafe(area, isMetric, precision) {
    const safePrecision = L.Util.extend({
      km: 2, ha: 2, m: 0, mi: 2, ac: 2, yd: 0, ft: 0, nm: 2,
    }, precision || {});

    if (isMetric) {
      let units = ['ha', 'm'];
      const metricType = typeof isMetric;
      if (metricType === 'string') units = [isMetric];
      else if (metricType !== 'boolean') units = isMetric;

      if (area >= 1000000 && units.indexOf('km') !== -1) {
        return `${L.GeometryUtil.formattedNumber(area * 0.000001, safePrecision.km)} km²`;
      }
      if (area >= 10000 && units.indexOf('ha') !== -1) {
        return `${L.GeometryUtil.formattedNumber(area * 0.0001, safePrecision.ha)} ha`;
      }
      return `${L.GeometryUtil.formattedNumber(area, safePrecision.m)} m²`;
    }

    const areaYards = area / 0.836127;
    if (areaYards >= 3097600) {
      return `${L.GeometryUtil.formattedNumber(areaYards / 3097600, safePrecision.mi)} mi²`;
    }
    if (areaYards >= 4840) {
      return `${L.GeometryUtil.formattedNumber(areaYards / 4840, safePrecision.ac)} acres`;
    }
    return `${L.GeometryUtil.formattedNumber(areaYards, safePrecision.yd)} yd²`;
  };
}

// ── Custom colored DivIcon ──
function createColorIcon(color, selected = false) {
  const size = selected ? 32 : 24;
  const border = selected ? '4px solid #FBBF24' : '3px solid white';
  return new L.DivIcon({
    html: `<div style="
      background:${color}; width:${size}px; height:${size}px; border-radius:50%;
      border:${border}; box-shadow:0 2px 6px rgba(0,0,0,.35);
      display:flex; align-items:center; justify-content:center;">
      <svg width="${size * 0.5}" height="${size * 0.5}" viewBox="0 0 24 24" fill="white">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
      </svg>
    </div>`,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  });
}

const STATUS_COLORS = {
  pendiente: '#94A3B8',
  visitado_habido: '#22C55E',
  visitado_no_habido: '#F59E0B',
  fallecido_inubicable: '#EF4444',
  suplantacion: '#E11D48',
  pago_no_registrado: '#3B82F6',
};

const STATUS_LABELS = {
  pendiente: 'Pendiente',
  visitado_habido: 'Habido',
  visitado_no_habido: 'No Habido',
  fallecido_inubicable: 'Inubicable',
  suplantacion: 'Suplantación',
  pago_no_registrado: 'Pago NR',
};

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

// ── Point-in-polygon (ray casting) ──
function pointInPolygon(lat, lng, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0], yi = polygon[i][1];
    const xj = polygon[j][0], yj = polygon[j][1];
    const intersect = ((yi > lng) !== (yj > lng)) &&
      (lat < (xj - xi) * (lng - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

// ── Drawing controls component ──
function DrawingControls({ onShapeCreated, onClear }) {
  const map = useMap();
  const drawControlRef = useRef(null);

  useEffect(() => {
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    const drawControl = new L.Control.Draw({
      position: 'topright',
      draw: {
        polyline: false,
        marker: false,
        circlemarker: false,
        rectangle: {
          shapeOptions: {
            color: '#6366F1',
            weight: 2,
            fillOpacity: 0.15,
          },
        },
        polygon: {
          allowIntersection: false,
          shapeOptions: {
            color: '#6366F1',
            weight: 2,
            fillOpacity: 0.15,
          },
        },
        circle: {
          shapeOptions: {
            color: '#6366F1',
            weight: 2,
            fillOpacity: 0.15,
          },
        },
      },
      edit: {
        featureGroup: drawnItems,
        remove: true,
      },
    });

    map.addControl(drawControl);
    drawControlRef.current = { drawControl, drawnItems };

    const handleCreated = (e) => {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);

      const type = e.layerType;
      if (type === 'circle') {
        const center = e.layer.getLatLng();
        const radius = e.layer.getRadius(); // meters
        onShapeCreated({ type: 'circle', center: [center.lat, center.lng], radiusM: radius });
      } else if (type === 'polygon' || type === 'rectangle') {
        const latlngs = e.layer.getLatLngs()[0].map(ll => [ll.lat, ll.lng]);
        onShapeCreated({ type: 'polygon', points: latlngs });
      }
    };

    const handleDeleted = () => {
      onClear();
    };

    map.on(L.Draw.Event.CREATED, handleCreated);
    map.on(L.Draw.Event.DELETED, handleDeleted);

    return () => {
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.off(L.Draw.Event.DELETED, handleDeleted);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
    };
  }, [map, onShapeCreated, onClear]);

  return null;
}

// ── Auto-fit bounds ──
function FitBounds({ markers }) {
  const map = useMap();
  useEffect(() => {
    if (markers.length > 0) {
      const bounds = L.latLngBounds(markers.map(m => [m.lat, m.lng]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }
  }, [markers.length]);
  return null;
}

export default function MapRoutePage({ user, userData, onBack }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [shape, setShape] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showUnlocated, setShowUnlocated] = useState(false);
  const [routeDate, setRouteDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [existingRoute, setExistingRoute] = useState(null);
  const [saveMsg, setSaveMsg] = useState('');

  const gestorSecciones = userData?.secciones || [];
  const gestorSeccion = userData?.seccion || '';

  // ── Load geolocated clients ──
  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      const campaignId = await getActiveCampaignId();
      if (!campaignId) { setLoading(false); return; }

      const sectionsToLoad = gestorSecciones.length > 0
        ? gestorSecciones
        : (gestorSeccion ? [gestorSeccion] : []);

      const clientMap = new Map();
      for (const secId of sectionsToLoad) {
        const snap = await getDocs(
          collection(db, 'campañas', campaignId, 'gestores', secId, 'clientes')
        );
        snap.forEach(d => {
          const data = { id: d.id, campaignId, seccion_key: secId, ...d.data() };
          const key = data.numero_documento || d.id;
          const existing = clientMap.get(key);
          if (!existing || (data.estado_gestion && data.estado_gestion !== 'pendiente')) {
            clientMap.set(key, data);
          }
        });
      }

      setClients([...clientMap.values()]);

      // Check for existing route on this date
      if (user?.uid) {
        const route = await getRoute(routeDate, user.uid);
        if (route) {
          setExistingRoute(route);
          const routeClientIds = new Set(route.clientes.map(c => c.codigo_cliente));
          setSelectedIds(routeClientIds);
        }
      }
    } catch (err) {
      console.error('Error loading clients for map:', err);
    } finally {
      setLoading(false);
    }
  }, [gestorSecciones.join(','), gestorSeccion, routeDate, user?.uid]);

  useEffect(() => { loadClients(); }, [loadClients]);

  // ── Clients with GPS coordinates ──
  const geoClients = useMemo(() => {
    return clients
      .map(c => {
        const loc = c.ubicacion_verificada;
        const verifiedLat = Number(loc?.lat || 0);
        const verifiedLng = Number(loc?.lng || 0);
        const excelLat = Number(c.coordenada_y || 0);
        const excelLng = Number(c.coordenada_x || 0);

        if (verifiedLat && verifiedLng) {
          return { ...c, lat: verifiedLat, lng: verifiedLng, location_source: 'verificada' };
        }
        if (excelLat && excelLng) {
          return { ...c, lat: excelLat, lng: excelLng, location_source: 'excel' };
        }
        return null;
      })
      .filter(Boolean);
  }, [clients]);

  const unlocatedCount = clients.length - geoClients.length;

  // ── Filter clients for marker display ──
  const visibleClients = useMemo(() => {
    let filtered = geoClients;
    if (statusFilter !== 'all') {
      filtered = filtered.filter(c => (c.estado_gestion || 'pendiente') === statusFilter);
    }
    if (search) {
      const term = search.toLowerCase();
      filtered = filtered.filter(c =>
        (c.nombre_completo || '').toLowerCase().includes(term) ||
        (c.numero_documento || '').includes(term) ||
        (c.distrito || '').toLowerCase().includes(term)
      );
    }
    return filtered;
  }, [geoClients, statusFilter, search]);

  // ── Apply shape selection ──
  const handleShapeCreated = useCallback((newShape) => {
    setShape(newShape);
    const newSelected = new Set(selectedIds);

    visibleClients.forEach(c => {
      let inside = false;
      if (newShape.type === 'circle') {
        const dist = haversineKm(c.lat, c.lng, newShape.center[0], newShape.center[1]) * 1000;
        inside = dist <= newShape.radiusM;
      } else if (newShape.type === 'polygon') {
        inside = pointInPolygon(c.lat, c.lng, newShape.points);
      }
      if (inside) newSelected.add(c.id);
    });

    setSelectedIds(newSelected);
  }, [visibleClients, selectedIds]);

  const handleClearShape = useCallback(() => {
    setShape(null);
  }, []);

  // ── Toggle individual client ──
  const toggleClient = (clientId) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(clientId)) next.delete(clientId);
      else next.add(clientId);
      return next;
    });
  };

  // ── Select all visible / clear all ──
  const selectAllVisible = () => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      visibleClients.forEach(c => next.add(c.id));
      return next;
    });
  };

  const clearSelection = () => setSelectedIds(new Set());

  // ── Save route ──
  const handleSaveRoute = async () => {
    if (selectedIds.size === 0) return;
    setSaving(true);
    setSaveMsg('');
    try {
      const geoById = new Map(geoClients.map(c => [c.id, c]));
      const selectedClients = clients
        .filter(c => selectedIds.has(c.id))
        .map(c => ({
          ...(geoById.get(c.id) || {}),
          codigo_cliente: c.id,
          nombre: c.nombre_completo || '',
          seccion_key: c.seccion_key || '',
          lat: Number(c.ubicacion_verificada?.lat || geoById.get(c.id)?.lat || 0) || null,
          lng: Number(c.ubicacion_verificada?.lng || geoById.get(c.id)?.lng || 0) || null,
          estado: c.estado_gestion || 'pendiente',
          importe_deuda: parseFloat(c.importe_deuda_asignada) || 0,
        }));

      await saveRoute({
        gestorUid: user.uid,
        gestorNombre: userData?.nombre || user.email || '',
        fecha: routeDate,
        clientes: selectedClients,
      });

      setSaveMsg(`✓ Ruta guardada: ${selectedClients.length} clientes para ${routeDate}`);
      setExistingRoute({ clientes: selectedClients, total: selectedClients.length });
    } catch (err) {
      console.error('Error saving route:', err);
      const msg = String(err?.message || '');
      if (msg.includes('Missing or insufficient permissions')) {
        setSaveMsg('No tiene permisos para guardar esta ruta. Verifique su sesión y rol.');
      } else {
        setSaveMsg('Error al guardar la ruta. Intente nuevamente.');
      }
    } finally {
      setSaving(false);
    }
  };

  // ── Map center ──
  const mapCenter = useMemo(() => {
    if (geoClients.length > 0) {
      const lats = geoClients.map(c => c.lat);
      const lngs = geoClients.map(c => c.lng);
      return [(Math.min(...lats) + Math.max(...lats)) / 2, (Math.min(...lngs) + Math.max(...lngs)) / 2];
    }
    return [-12.0464, -77.0428]; // Lima default
  }, [geoClients]);

  // ── Selected clients summary ──
  const selectedSummary = useMemo(() => {
    const sel = clients.filter(c => selectedIds.has(c.id));
    const deuda = sel.reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0);
    const pending = sel.filter(c => (c.estado_gestion || 'pendiente') === 'pendiente').length;
    return { count: sel.length, deuda, pending };
  }, [clients, selectedIds]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={28} className="animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="app-page flex flex-col">
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
              <MapPin size={18} />
            </div>
            <div>
              <h1 className="app-topbar-title">Mapa de Clientes</h1>
              <p className="app-topbar-subtitle">
                {geoClients.length} con GPS · {unlocatedCount} sin ubicación
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadClients}
              className="p-2.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all border border-slate-200">
              <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col lg:flex-row">
        {/* Sidebar: Controls */}
        <div className="w-full lg:w-80 shrink-0 p-4 space-y-4 overflow-y-auto lg:max-h-[calc(100vh-60px)]">
          {/* Date selector */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5 mb-2">
              <Calendar size={14} /> Fecha de Ruta
            </label>
            <input
              type="date"
              value={routeDate}
              onChange={e => setRouteDate(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2
                       focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
            {existingRoute && (
              <p className="text-xs text-indigo-600 mt-2 font-medium">
                Ruta existente: {existingRoute.total} clientes
              </p>
            )}
          </div>

          {/* Filters */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-3">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
              <Filter size={14} /> Filtros
            </label>

            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Buscar nombre, DNI, distrito..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm
                         focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              />
            </div>

            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm
                       focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            >
              <option value="all">Todos los estados</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {/* Selection summary */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
                <Users size={14} /> Selección
              </label>
              <span className="text-lg font-bold text-indigo-600">{selectedSummary.count}</span>
            </div>

            {selectedSummary.count > 0 && (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Pendientes</span>
                  <span className="font-semibold text-gray-900">{selectedSummary.pending}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Deuda total</span>
                  <span className="font-semibold text-gray-900">
                    S/ {selectedSummary.deuda.toLocaleString('es-PE', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={selectAllVisible}
                className="flex-1 text-xs px-3 py-2 bg-indigo-50 text-indigo-700 rounded-lg
                         font-medium hover:bg-indigo-100 transition-all border border-indigo-200"
              >
                Seleccionar visibles
              </button>
              <button
                onClick={clearSelection}
                className="text-xs px-3 py-2 bg-slate-50 text-slate-600 rounded-lg
                         font-medium hover:bg-slate-100 transition-all border border-slate-200"
              >
                <Trash2 size={13} />
              </button>
            </div>
          </div>

          {/* Drawing instruction */}
          <div className="bg-violet-50 rounded-xl border border-violet-200 p-4 shadow-sm">
            <p className="text-xs text-violet-700 font-medium mb-1">Herramientas de dibujo</p>
            <p className="text-xs text-violet-600">
              Use los controles del mapa (arriba a la derecha) para dibujar un <strong>rectángulo</strong>,{' '}
              <strong>polígono</strong> o <strong>círculo</strong>. Los clientes dentro del área se agregarán
              a la selección automáticamente.
            </p>
          </div>

          {/* Save route button */}
          <button
            onClick={handleSaveRoute}
            disabled={saving || selectedSummary.count === 0}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 text-white
                     rounded-xl font-semibold text-sm hover:bg-indigo-700 transition-all
                     disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Guardar Ruta ({selectedSummary.count} clientes)
          </button>

          {saveMsg && (
            <p className={`text-xs font-medium text-center ${saveMsg.startsWith('✓') ? 'text-emerald-600' : 'text-red-600'}`}>
              {saveMsg}
            </p>
          )}
        </div>

        {/* Map */}
        <div className="flex-1 min-h-[400px] lg:min-h-0 relative">
          {geoClients.length === 0 ? (
            <div className="flex items-center justify-center h-full bg-slate-100">
              <div className="text-center p-8">
                <MapPin size={40} className="text-gray-300 mx-auto mb-4" />
                <p className="text-gray-600 font-semibold">Sin clientes geolocalizados</p>
                <p className="text-sm text-gray-400 mt-1">
                  Visite clientes desde el Dashboard para guardar sus coordenadas GPS.
                </p>
              </div>
            </div>
          ) : (
            <MapContainer
              center={mapCenter}
              zoom={13}
              style={{ width: '100%', height: '100%', minHeight: '500px' }}
              className="z-0"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <DrawingControls onShapeCreated={handleShapeCreated} onClear={handleClearShape} />
              <FitBounds markers={geoClients} />

              {visibleClients.map(c => {
                const isSelected = selectedIds.has(c.id);
                const status = c.estado_gestion || 'pendiente';
                const color = STATUS_COLORS[status] || '#94A3B8';

                return (
                  <Marker
                    key={c.id}
                    position={[c.lat, c.lng]}
                    icon={createColorIcon(color, isSelected)}
                    eventHandlers={{
                      click: () => toggleClient(c.id),
                    }}
                  >
                    <Popup>
                      <div className="text-sm min-w-[200px]">
                        <p className="font-bold text-gray-900">{c.nombre_completo || 'Sin nombre'}</p>
                        <p className="text-gray-500 text-xs">{c.numero_documento}</p>
                        <div className="mt-2 space-y-1">
                          <p className="text-xs">
                            <span className="text-gray-500">Estado:</span>{' '}
                            <span className="font-medium" style={{ color }}>
                              {STATUS_LABELS[status] || status}
                            </span>
                          </p>
                          <p className="text-xs">
                            <span className="text-gray-500">Deuda:</span>{' '}
                            <span className="font-medium">
                              S/ {(parseFloat(c.importe_deuda_asignada) || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}
                            </span>
                          </p>
                          <p className="text-xs">
                            <span className="text-gray-500">Distrito:</span>{' '}
                            {c.distrito || '—'}
                          </p>
                          <p className="text-xs">
                            <span className="text-gray-500">Fuente:</span>{' '}
                            {c.location_source === 'verificada' ? 'GPS verificado' : 'Excel'}
                          </p>
                          <p className="text-xs text-gray-400">
                            {c.direccion || ''}
                          </p>
                        </div>
                        <a
                          href={`https://www.google.com/maps?q=${c.lat},${c.lng}`}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 block w-full text-center text-xs px-2 py-1.5 rounded
                                     bg-emerald-100 text-emerald-700 border border-emerald-200 font-medium"
                        >
                          Abrir en Google Maps
                        </a>
                        <button
                          onClick={() => toggleClient(c.id)}
                          className={`mt-2 w-full text-xs px-2 py-1.5 rounded font-medium transition-all
                            ${isSelected
                              ? 'bg-amber-100 text-amber-700 border border-amber-200'
                              : 'bg-indigo-100 text-indigo-700 border border-indigo-200'
                            }`}
                        >
                          {isSelected ? 'Quitar de ruta' : 'Agregar a ruta'}
                        </button>
                      </div>
                    </Popup>
                  </Marker>
                );
              })}
            </MapContainer>
          )}

          {/* Legend overlay */}
          <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur rounded-lg border border-slate-200 p-3 shadow-lg z-[500]">
            <p className="text-xs font-semibold text-gray-500 mb-2">Estado</p>
            <div className="space-y-1">
              {Object.entries(STATUS_LABELS).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: STATUS_COLORS[k] }} />
                  <span className="text-xs text-gray-600">{v}</span>
                </div>
              ))}
            </div>
            <div className="mt-2 pt-2 border-t border-slate-100 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full border-2 border-amber-400 bg-gray-300" />
              <span className="text-xs text-gray-600">Seleccionado</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
