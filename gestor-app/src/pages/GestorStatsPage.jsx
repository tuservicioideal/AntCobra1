import { useState, useEffect, useCallback, useMemo } from 'react';
import { collection, getDocs } from 'firebase/firestore';
import { db } from '../services/firebase';
import { getActiveCampaignId } from '../services/campaignUtils';
import { getRoutesForGestor } from '../services/routeService';
import {
  DonutChart, GaugeChart, StackedBar, BarChartVertical, Legend,
  KPICard as SharedKPICard,
} from '../components/Charts';
import {
  ArrowLeft, Users, BarChart3, DollarSign, TrendingUp, RefreshCw, Loader2,
  CheckCircle2, Clock, MapPin, Route, ChevronUp, Eye, Target, Zap
} from 'lucide-react';

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
  pago_no_registrado: 'Pago No Reg.',
};

const RANK_COLORS = ['#4F46E5', '#7C3AED', '#2563EB', '#0D9488', '#059669', '#D97706', '#DC2626', '#9333EA'];

function Card({ children, className = '' }) {
  return <div className={`bg-white border border-slate-200 rounded-2xl shadow-sm ${className}`}>{children}</div>;
}
function CardHeader({ icon, title, subtitle }) {
  return (
    <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2.5">
      {icon}
      <div>
        <h3 className="text-sm font-bold text-gray-900">{title}</h3>
        {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function GestorStatsPage({ user, userData, onBack }) {
  const [gestores, setGestores] = useState([]);
  const [gestorStats, setGestorStats] = useState({});
  const [routeStats, setRouteStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedGestor, setSelectedGestor] = useState(null);
  const [dateRange, setDateRange] = useState({
    from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    to: new Date().toISOString().slice(0, 10),
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const campaignId = await getActiveCampaignId();
      if (!campaignId) { setLoading(false); return; }

      const usersSnap = await getDocs(collection(db, 'usuarios'));
      const gestorList = [];
      usersSnap.forEach(d => {
        const u = { id: d.id, ...d.data() };
        if (u.activo !== false && (u.seccion || (u.secciones && u.secciones.length > 0))) {
          gestorList.push(u);
        }
      });
      const byEmail = {};
      for (const g of gestorList) {
        const email = (g.email || '').toLowerCase();
        if (!email) continue;
        if (!byEmail[email] || (g.uid && !byEmail[email].uid)) byEmail[email] = g;
      }
      setGestores(Object.values(byEmail));

      const gestoresSnap = await getDocs(collection(db, 'campañas', campaignId, 'gestores'));
      const statsMap = {};
      const sectionToGestor = {};
      for (const g of Object.values(byEmail)) {
        const secs = g.secciones || (g.seccion ? [g.seccion] : []);
        for (const s of secs) sectionToGestor[s] = g.id;
      }

      for (const gestorDoc of gestoresSnap.docs) {
        const secId = gestorDoc.id;
        const gestorId = sectionToGestor[secId];
        if (!gestorId) continue;
        if (!statsMap[gestorId]) {
          statsMap[gestorId] = {
            total: 0, pendiente: 0, habido: 0, noHabido: 0, inubicable: 0,
            suplantacion: 0, pagoNoReg: 0, deuda: 0, deudaPend: 0,
            deudaGestionada: 0, geolocated: 0, secciones: [],
          };
        }
        statsMap[gestorId].secciones.push(secId);
        const clientsSnap = await getDocs(
          collection(db, 'campañas', campaignId, 'gestores', secId, 'clientes')
        );
        const clientMap = new Map();
        clientsSnap.forEach(d => {
          const c = { id: d.id, ...d.data() };
          const key = c.numero_documento || d.id;
          const existing = clientMap.get(key);
          if (!existing || (c.estado_gestion && c.estado_gestion !== 'pendiente')) clientMap.set(key, c);
        });
        for (const c of clientMap.values()) {
          const st = statsMap[gestorId];
          const estado = c.estado_gestion || 'pendiente';
          st.total++;
          if (estado === 'pendiente') st.pendiente++;
          else if (estado === 'visitado_habido') st.habido++;
          else if (estado === 'visitado_no_habido') st.noHabido++;
          else if (estado === 'fallecido_inubicable') st.inubicable++;
          else if (estado === 'suplantacion') st.suplantacion++;
          else if (estado === 'pago_no_registrado') st.pagoNoReg++;
          st.deuda += parseFloat(c.importe_deuda_asignada) || 0;
          st.deudaPend += parseFloat(c.importe_deuda_pendiente) || 0;
          if (estado !== 'pendiente') st.deudaGestionada += parseFloat(c.importe_deuda_asignada) || 0;
          if (c.ubicacion_verificada && c.ubicacion_verificada.lat) st.geolocated++;
        }
      }
      setGestorStats(statsMap);

      const routeMap = {};
      for (const g of Object.values(byEmail)) {
        try {
          const routes = await getRoutesForGestor(g.id);
          const filtered = routes.filter(r => r.fecha >= dateRange.from && r.fecha <= dateRange.to);
          routeMap[g.id] = {
            totalRoutes: filtered.length,
            totalPlanned: filtered.reduce((s, r) => s + (r.total || 0), 0),
            totalCompleted: filtered.reduce((s, r) => s + (r.completados || 0), 0),
          };
        } catch { routeMap[g.id] = { totalRoutes: 0, totalPlanned: 0, totalCompleted: 0 }; }
      }
      setRouteStats(routeMap);
    } catch (err) {
      console.error('Error loading gestor stats:', err);
    } finally {
      setLoading(false);
    }
  }, [dateRange.from, dateRange.to]);

  useEffect(() => { loadData(); }, [loadData]);

  const ranking = useMemo(() => {
    return gestores
      .filter(g => gestorStats[g.id])
      .map(g => {
        const st = gestorStats[g.id];
        const avance = st.total > 0 ? ((st.total - st.pendiente) / st.total) * 100 : 0;
        const rt = routeStats[g.id] || {};
        return { ...g, ...st, avance, ...rt };
      })
      .sort((a, b) => b.avance - a.avance);
  }, [gestores, gestorStats, routeStats]);

  const global = useMemo(() => {
    const t = { total: 0, pendiente: 0, habido: 0, noHabido: 0, inubicable: 0, suplantacion: 0, pagoNoReg: 0, deuda: 0, deudaGestionada: 0, geolocated: 0, routes: 0, routeCompleted: 0 };
    for (const g of ranking) {
      t.total += g.total; t.pendiente += g.pendiente; t.habido += g.habido;
      t.noHabido += g.noHabido; t.inubicable += g.inubicable;
      t.suplantacion += g.suplantacion || 0; t.pagoNoReg += g.pagoNoReg || 0;
      t.deuda += g.deuda; t.deudaGestionada += g.deudaGestionada;
      t.geolocated += g.geolocated; t.routes += g.totalRoutes || 0;
      t.routeCompleted += g.totalCompleted || 0;
    }
    t.avance = t.total > 0 ? Math.round(((t.total - t.pendiente) / t.total) * 100) : 0;
    return t;
  }, [ranking]);

  if (loading) {
    return <div className="flex items-center justify-center py-32"><Loader2 size={28} className="animate-spin text-indigo-500" /></div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 text-white sticky top-0 z-[1000] shadow-lg shadow-purple-500/20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {onBack && (
              <button onClick={onBack} className="p-2 bg-white/10 hover:bg-white/20 rounded-xl transition-all border border-white/10">
                <ArrowLeft size={18} />
              </button>
            )}
            <div>
              <h1 className="text-lg font-extrabold tracking-tight flex items-center gap-2">
                <BarChart3 size={18} className="text-purple-200" />
                Métricas por Gestor
              </h1>
              <p className="text-purple-200 text-xs font-medium">{ranking.length} gestores · {global.total} clientes</p>
            </div>
          </div>
          <button onClick={loadData} className="p-2.5 bg-white/10 hover:bg-white/20 rounded-xl transition-all border border-white/10">
            <RefreshCw size={17} />
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-4 space-y-6">
        {/* Date filter */}
        <Card className="p-4 flex flex-wrap items-end gap-4">
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Desde</label>
            <input type="date" value={dateRange.from} onChange={e => setDateRange(p => ({ ...p, from: e.target.value }))}
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 outline-none" />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Hasta</label>
            <input type="date" value={dateRange.to} onChange={e => setDateRange(p => ({ ...p, to: e.target.value }))}
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 outline-none" />
          </div>
        </Card>

        {/* Gauge + KPIs */}
        <div className="grid md:grid-cols-3 gap-4">
          <Card className="p-5 flex flex-col items-center">
            <GaugeChart value={global.avance} max={100} label="AVANCE GLOBAL" size={200} color="#7C3AED"
              zones={[{ from: 0, to: 30, color: '#EF4444' }, { from: 30, to: 70, color: '#F59E0B' }, { from: 70, to: 100, color: '#22C55E' }]} />
            <p className="text-xs text-gray-500 mt-2">{global.total - global.pendiente} de {global.total} gestionados</p>
          </Card>
          <Card className="p-5 flex flex-col items-center">
            <DonutChart
              slices={Object.entries(STATUS_LABELS).map(([k, v]) => ({
                value: global[k === 'visitado_habido' ? 'habido' : k === 'visitado_no_habido' ? 'noHabido' : k === 'fallecido_inubicable' ? 'inubicable' : k] || 0,
                color: STATUS_COLORS[k], label: v,
              }))}
              size={180} thickness={30} centerLabel="TOTAL" centerValue={global.total}
            />
            <div className="mt-3">
              <Legend items={Object.entries(STATUS_LABELS).slice(0, 4).map(([k, v]) => ({ color: STATUS_COLORS[k], label: v }))} />
            </div>
          </Card>
          <div className="grid grid-cols-2 gap-3">
            <SharedKPICard icon={<Users size={16} />} value={global.total} label="Clientes" color="indigo" />
            <SharedKPICard icon={<CheckCircle2 size={16} />} value={global.habido} label="Habidos" color="emerald" />
            <SharedKPICard icon={<MapPin size={16} />} value={global.geolocated} label="Con GPS" color="teal" />
            <SharedKPICard icon={<Route size={16} />} value={global.routes} label="Rutas" color="purple" />
            <SharedKPICard icon={<DollarSign size={16} />} value={`S/ ${(global.deudaGestionada / 1000).toFixed(0)}K`} label="Gestionada" color="rose" small />
            <SharedKPICard icon={<Target size={16} />} value={global.routeCompleted} label="Visitas OK" color="green" />
          </div>
        </div>

        {/* Stacked bars per gestor */}
        <Card>
          <CardHeader icon={<BarChart3 size={16} className="text-purple-500" />} title="Desglose por Gestor" subtitle="Distribución de estados por cada gestor" />
          <div className="p-6 space-y-4">
            <Legend items={Object.entries(STATUS_LABELS).map(([k, v]) => ({ color: STATUS_COLORS[k], label: v }))} />
            {ranking.map(g => (
              <StackedBar key={g.id}
                label={g.nombre || g.email || g.id.slice(0, 12)}
                total={g.total}
                segments={[
                  { value: g.pendiente, color: STATUS_COLORS.pendiente },
                  { value: g.habido, color: STATUS_COLORS.visitado_habido },
                  { value: g.noHabido, color: STATUS_COLORS.visitado_no_habido },
                  { value: g.inubicable, color: STATUS_COLORS.fallecido_inubicable },
                  { value: g.suplantacion || 0, color: STATUS_COLORS.suplantacion },
                  { value: g.pagoNoReg || 0, color: STATUS_COLORS.pago_no_registrado },
                ]}
              />
            ))}
          </div>
        </Card>

        {/* Avance comparison bar chart */}
        <Card>
          <CardHeader icon={<TrendingUp size={16} className="text-purple-500" />} title="Comparativa de Avance" subtitle="Porcentaje de gestión por gestor" />
          <div className="p-6">
            <BarChartVertical
              bars={ranking.map((g, i) => ({
                label: (g.nombre || g.email || '').split(' ')[0] || g.id.slice(0, 6),
                value: Math.round(g.avance),
                color: g.avance >= 70 ? '#22C55E' : g.avance >= 40 ? '#F59E0B' : '#EF4444',
              }))}
              height={200}
            />
            <p className="text-xs text-gray-400 text-center mt-2">% de Avance</p>
          </div>
        </Card>

        {/* Ranking table */}
        <Card>
          <CardHeader icon={<TrendingUp size={16} className="text-purple-500" />} title="Ranking de Gestores" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60">
                  {['#', 'Gestor', 'Secciones', 'Clientes', 'Pendientes', 'Habidos', 'GPS', 'Rutas', 'Deuda', 'Avance'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ranking.map((g, idx) => {
                  const avancePct = Math.round(g.avance);
                  return (
                    <tr key={g.id}
                      className={`hover:bg-purple-50/30 transition-colors cursor-pointer ${selectedGestor === g.id ? 'bg-purple-50' : ''}`}
                      onClick={() => setSelectedGestor(selectedGestor === g.id ? null : g.id)}>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${idx === 0 ? 'bg-amber-100 text-amber-700' : idx === 1 ? 'bg-slate-200 text-slate-700' : idx === 2 ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'}`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-semibold text-gray-900 truncate max-w-[160px]">{g.nombre || g.email || '—'}</p>
                        <p className="text-xs text-gray-400 truncate">{g.email || ''}</p>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {(g.secciones || []).map(s => (
                            <span key={s} className="text-xs bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded font-medium">{s}</span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-semibold text-gray-900">{g.total}</td>
                      <td className="px-4 py-3 text-gray-600">{g.pendiente}</td>
                      <td className="px-4 py-3 text-emerald-600 font-medium">{g.habido}</td>
                      <td className="px-4 py-3"><span className="text-teal-600 font-medium">{g.geolocated}</span><span className="text-gray-400 text-xs">/{g.total}</span></td>
                      <td className="px-4 py-3 text-purple-600 font-medium">{g.totalRoutes || 0}</td>
                      <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">S/ {g.deuda.toLocaleString('es-PE', { maximumFractionDigits: 0 })}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${avancePct}%`, backgroundColor: avancePct >= 70 ? '#22C55E' : avancePct >= 40 ? '#F59E0B' : '#EF4444' }} />
                          </div>
                          <span className="text-xs font-bold text-gray-700">{avancePct}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Expanded gestor detail */}
        {selectedGestor && (() => {
          const g = ranking.find(r => r.id === selectedGestor);
          if (!g) return null;
          const rt = routeStats[g.id] || {};
          const avancePct = Math.round(g.avance);
          return (
            <Card className="border-2 border-purple-200 shadow-md">
              <div className="px-6 py-4 border-b border-purple-100 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-gray-900">{g.nombre || g.email}</h3>
                  <p className="text-sm text-gray-500">Secciones: {(g.secciones || []).join(', ')}</p>
                </div>
                <button onClick={() => setSelectedGestor(null)} className="p-2 hover:bg-gray-100 rounded-lg transition-all">
                  <ChevronUp size={18} className="text-gray-400" />
                </button>
              </div>
              <div className="p-6">
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  <DetailCard label="Clientes" value={g.total} sub={`${g.pendiente} pendientes`} />
                  <DetailCard label="Geolocalizados" value={g.geolocated} sub={`de ${g.total} total`} />
                  <DetailCard label="Rutas" value={rt.totalRoutes || 0} sub={`${rt.totalCompleted || 0} visitas OK`} />
                  <DetailCard label="Deuda gestionada" value={`S/ ${(g.deudaGestionada || 0).toLocaleString('es-PE', { maximumFractionDigits: 0 })}`} sub={`de S/ ${(g.deuda || 0).toLocaleString('es-PE', { maximumFractionDigits: 0 })}`} />
                </div>
                <div className="flex flex-col sm:flex-row items-center gap-8">
                  <DonutChart
                    slices={[
                      { value: g.habido, color: '#22C55E', label: 'Habido' },
                      { value: g.noHabido, color: '#F59E0B', label: 'No Habido' },
                      { value: g.inubicable, color: '#EF4444', label: 'Inubicable' },
                      { value: g.suplantacion || 0, color: '#E11D48', label: 'Suplantación' },
                      { value: g.pagoNoReg || 0, color: '#3B82F6', label: 'Pago NR' },
                      { value: g.pendiente, color: '#94A3B8', label: 'Pendiente' },
                    ]}
                    size={170} thickness={28} centerLabel="AVANCE" centerValue={`${avancePct}%`}
                  />
                  <div className="space-y-2 flex-1">
                    {[
                      { label: 'Habido', value: g.habido, color: '#22C55E' },
                      { label: 'No Habido', value: g.noHabido, color: '#F59E0B' },
                      { label: 'Inubicable', value: g.inubicable, color: '#EF4444' },
                      { label: 'Pendiente', value: g.pendiente, color: '#94A3B8' },
                    ].filter(s => s.value > 0).map(s => (
                      <div key={s.label} className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: s.color }} />
                        <span className="text-sm text-gray-600 flex-1">{s.label}</span>
                        <span className="text-sm font-bold text-gray-900">{s.value}</span>
                        <span className="text-xs text-gray-400">{g.total > 0 ? Math.round((s.value / g.total) * 100) : 0}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          );
        })()}
      </div>
    </div>
  );
}

function DetailCard({ label, value, sub }) {
  return (
    <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}
