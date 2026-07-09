import { useState, useEffect, useCallback, useMemo } from 'react';
import { collection, getDocs } from 'firebase/firestore';
import { db } from '../services/firebase';
import { getActiveCampaignId } from '../services/campaignUtils';
import {
  DonutChart, GaugeChart, StackedBar, BarChartVertical, TreeMap,
  FunnelChart, Legend, KPICard,
} from '../components/Charts';
import {
  BarChart3, PieChart, Users, DollarSign, TrendingUp, RefreshCw,
  Loader2, CheckCircle2, Clock, AlertTriangle, Eye, MapPin, Target,
  Zap, ShieldAlert, Filter
} from 'lucide-react';

// Color palette
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

const AGING_RANGES = [
  { label: '0-30 días', min: 0, max: 30, color: '#22C55E' },
  { label: '31-60 días', min: 31, max: 60, color: '#F59E0B' },
  { label: '61-90 días', min: 61, max: 90, color: '#F97316' },
  { label: '91-180 días', min: 91, max: 180, color: '#EF4444' },
  { label: '180+ días', min: 181, max: Infinity, color: '#991B1B' },
];

const PALETTE = [
  '#4F46E5', '#7C3AED', '#2563EB', '#0D9488', '#059669',
  '#D97706', '#DC2626', '#9333EA', '#0891B2', '#CA8A04',
  '#6366F1', '#EC4899', '#14B8A6', '#8B5CF6', '#F43F5E',
];

function TabBar({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 bg-slate-100 p-1 rounded-xl overflow-x-auto">
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={`px-4 py-2 text-sm font-semibold rounded-lg whitespace-nowrap transition-all ${
            active === t.id
              ? 'bg-white text-indigo-700 shadow-sm'
              : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
          }`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

function Card({ children, className = '' }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-2xl shadow-sm ${className}`}>
      {children}
    </div>
  );
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

export default function StatsPage({ user, userData }) {
  const [rawClients, setRawClients] = useState([]);
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const campaignId = await getActiveCampaignId();
      if (!campaignId) { setLoading(false); return; }

      const sectionMap = {};
      const allClients = [];

      const gestoresSnap = await getDocs(
        collection(db, 'campañas', campaignId, 'gestores')
      );
      for (const gestorDoc of gestoresSnap.docs) {
        const secId = gestorDoc.id;
        if (!sectionMap[secId]) sectionMap[secId] = new Map();
        const clientsSnap = await getDocs(
          collection(db, 'campañas', campaignId, 'gestores', secId, 'clientes')
        );
        clientsSnap.forEach((d) => {
          const c = { id: d.id, campaignId, seccion_key: secId, ...d.data() };
          const key = c.numero_documento || d.id;
          const existing = sectionMap[secId].get(key);
          if (!existing || (c.estado_gestion && c.estado_gestion !== 'pendiente')) {
            sectionMap[secId].set(key, c);
          }
        });
      }

      const secs = [];
      for (const [secId, clientMap] of Object.entries(sectionMap)) {
        const clients = [...clientMap.values()];
        clients.forEach(c => allClients.push(c));
        const total = clients.length;
        const estados = {};
        Object.keys(STATUS_LABELS).forEach(k => {
          estados[k] = clients.filter(c => (c.estado_gestion || 'pendiente') === k).length;
        });
        const deuda = clients.reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0);
        const deudaPend = clients.reduce((s, c) => s + (parseFloat(c.importe_deuda_pendiente) || 0), 0);
        const deudaGestionada = clients
          .filter(c => (c.estado_gestion || 'pendiente') !== 'pendiente')
          .reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0);
        const geolocated = clients.filter(c => c.ubicacion_verificada && c.ubicacion_verificada.lat).length;
        const avancePct = total > 0 ? Math.round(((total - estados.pendiente) / total) * 100) : 0;
        secs.push({ seccion: secId, total, ...estados, deuda, deudaPend, deudaGestionada, geolocated, avancePct });
      }
      secs.sort((a, b) => a.seccion.localeCompare(b.seccion));
      setSections(secs);
      setRawClients(allClients);
    } catch (err) {
      console.error('Error loading stats:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  const handleRefresh = async () => { setRefreshing(true); await loadData(); setRefreshing(false); };

  const m = useMemo(() => {
    const clients = rawClients;
    const T = clients.length || 1;

    const statusCounts = {};
    Object.keys(STATUS_LABELS).forEach(k => {
      statusCounts[k] = clients.filter(c => (c.estado_gestion || 'pendiente') === k).length;
    });
    const gestionados = T - statusCounts.pendiente;
    const avancePct = Math.round((gestionados / T) * 100);

    const deudaTotal = clients.reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0);
    const deudaPendiente = clients.reduce((s, c) => s + (parseFloat(c.importe_deuda_pendiente) || 0), 0);
    const deudaGestionada = clients
      .filter(c => (c.estado_gestion || 'pendiente') !== 'pendiente')
      .reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0);
    const recoveryRate = deudaTotal > 0 ? ((deudaTotal - deudaPendiente) / deudaTotal) * 100 : 0;

    const aging = AGING_RANGES.map(r => ({
      ...r,
      count: clients.filter(c => {
        const d = parseInt(c.dias_atraso) || 0;
        return d >= r.min && d <= r.max;
      }).length,
      deuda: clients.filter(c => {
        const d = parseInt(c.dias_atraso) || 0;
        return d >= r.min && d <= r.max;
      }).reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0),
    }));

    const deptMap = {};
    clients.forEach(c => {
      const d = c.departamento || 'Sin Depto.';
      if (!deptMap[d]) deptMap[d] = { count: 0, deuda: 0 };
      deptMap[d].count++;
      deptMap[d].deuda += parseFloat(c.importe_deuda_asignada) || 0;
    });
    const departments = Object.entries(deptMap)
      .map(([k, v]) => ({ label: k, value: v.count, deuda: v.deuda }))
      .sort((a, b) => b.value - a.value);

    const distMap = {};
    clients.forEach(c => {
      const d = c.distrito || 'Sin Distrito';
      if (!distMap[d]) distMap[d] = { count: 0, deuda: 0 };
      distMap[d].count++;
      distMap[d].deuda += parseFloat(c.importe_deuda_asignada) || 0;
    });
    const districts = Object.entries(distMap)
      .map(([k, v]) => ({ label: k, value: v.count, deuda: v.deuda }))
      .sort((a, b) => b.deuda - a.deuda)
      .slice(0, 15);

    const geolocated = clients.filter(c => c.ubicacion_verificada && c.ubicacion_verificada.lat).length;
    const gpsPct = Math.round((geolocated / T) * 100);

    const withPromise = clients.filter(c => c.fecha_promesa_pago || c.monto_promesa_pago);
    const promiseAmount = withPromise.reduce((s, c) => s + (parseFloat(c.monto_promesa_pago) || 0), 0);

    const nivel1Map = {};
    clients.filter(c => c.nivel_1).forEach(c => {
      const k = c.nivel_1;
      if (!nivel1Map[k]) nivel1Map[k] = 0;
      nivel1Map[k]++;
    });
    const contactResults = Object.entries(nivel1Map)
      .map(([k, v]) => ({ label: k, value: v }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);

    const channelMap = {};
    clients.filter(c => c.canal_gestion).forEach(c => {
      const k = c.canal_gestion;
      if (!channelMap[k]) channelMap[k] = 0;
      channelMap[k]++;
    });
    const channels = Object.entries(channelMap)
      .map(([k, v]) => ({ label: k, value: v }))
      .sort((a, b) => b.value - a.value);

    const segMap = {};
    clients.filter(c => c.segmentacion || c.segmento_cartera).forEach(c => {
      const k = c.segmentacion || c.segmento_cartera;
      if (!segMap[k]) segMap[k] = { count: 0, deuda: 0 };
      segMap[k].count++;
      segMap[k].deuda += parseFloat(c.importe_deuda_asignada) || 0;
    });
    const segments = Object.entries(segMap)
      .map(([k, v]) => ({ label: k, value: v.count, deuda: v.deuda }))
      .sort((a, b) => b.deuda - a.deuda);

    const topDebtors = [...clients]
      .sort((a, b) => (parseFloat(b.importe_deuda_asignada) || 0) - (parseFloat(a.importe_deuda_asignada) || 0))
      .slice(0, 20);

    const funnel = [
      { label: 'Total asignados', value: clients.length, color: '#6366F1' },
      { label: 'Gestionados', value: gestionados, color: '#8B5CF6' },
      { label: 'Contactados (habidos)', value: statusCounts.visitado_habido, color: '#22C55E' },
      { label: 'Con promesa de pago', value: withPromise.length, color: '#0D9488' },
    ];

    return {
      total: clients.length, statusCounts, gestionados, avancePct,
      deudaTotal, deudaPendiente, deudaGestionada, recoveryRate,
      aging, departments, districts, geolocated, gpsPct,
      promiseAmount, withPromise,
      contactResults, channels, segments, topDebtors, funnel,
    };
  }, [rawClients, sections]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={28} className="animate-spin text-indigo-500" />
      </div>
    );
  }

  if (rawClients.length === 0) {
    return (
      <div className="p-6">
        <div className="max-w-md mx-auto text-center py-20">
          <BarChart3 size={40} className="text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 font-semibold">No hay datos de campaña todavía</p>
          <p className="text-sm text-gray-400 mt-1">Distribuya la cartera desde la app de administración.</p>
        </div>
      </div>
    );
  }

  const TABS = [
    { id: 'overview', label: 'Vista General' },
    { id: 'debt', label: 'Análisis de Deuda' },
    { id: 'territory', label: 'Territorio' },
    { id: 'performance', label: 'Rendimiento' },
  ];

  return (
    <div className="p-4 sm:p-6 lg:p-0 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center gap-2.5">
            <BarChart3 size={24} className="text-indigo-500" />
            Centro de Inteligencia
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {m.total.toLocaleString()} clientes · {sections.length} secciones
          </p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing}
          className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 transition-all disabled:opacity-50 shadow-sm">
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          Actualizar
        </button>
      </div>

      {/* Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 flex flex-col items-center">
          <GaugeChart value={m.avancePct} max={100} label="AVANCE DE GESTIÓN" size={200} color="#6366F1"
            zones={[{ from: 0, to: 30, color: '#EF4444' }, { from: 30, to: 70, color: '#F59E0B' }, { from: 70, to: 100, color: '#22C55E' }]} />
          <p className="text-xs text-gray-500 mt-2">{m.gestionados.toLocaleString()} de {m.total.toLocaleString()} gestionados</p>
        </Card>
        <Card className="p-5 flex flex-col items-center">
          <GaugeChart value={Math.round(m.recoveryRate)} max={100} label="TASA DE RECUPERACIÓN" size={200} color="#0D9488"
            zones={[{ from: 0, to: 25, color: '#EF4444' }, { from: 25, to: 60, color: '#F59E0B' }, { from: 60, to: 100, color: '#22C55E' }]} />
          <p className="text-xs text-gray-500 mt-2">S/ {(m.deudaTotal - m.deudaPendiente).toLocaleString('es-PE', { maximumFractionDigits: 0 })} recuperado</p>
        </Card>
        <Card className="p-5 flex flex-col items-center">
          <GaugeChart value={m.gpsPct} max={100} label="COBERTURA GPS" size={200} color="#7C3AED" />
          <p className="text-xs text-gray-500 mt-2">{m.geolocated.toLocaleString()} de {m.total.toLocaleString()} geolocalizados</p>
        </Card>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard icon={<Users size={18} />} value={m.total.toLocaleString()} label="Total Cuentas" color="indigo" />
        <KPICard icon={<CheckCircle2 size={18} />} value={m.statusCounts.visitado_habido} label="Habidos" color="emerald" />
        <KPICard icon={<Eye size={18} />} value={m.statusCounts.visitado_no_habido} label="No Habidos" color="amber" />
        <KPICard icon={<DollarSign size={18} />} value={`S/ ${(m.deudaTotal / 1000).toFixed(0)}K`} label="Deuda Asignada" color="rose" small />
        <KPICard icon={<DollarSign size={18} />} value={`S/ ${(m.deudaGestionada / 1000).toFixed(0)}K`} label="Deuda Gestionada" color="violet" small />
        <KPICard icon={<Target size={18} />} value={`S/ ${(m.promiseAmount / 1000).toFixed(0)}K`} sub={`${m.withPromise.length} promesas`} label="Promesas de Pago" color="teal" small />
      </div>

      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {/* TAB: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader icon={<PieChart size={16} className="text-indigo-500" />} title="Distribución por Estado" subtitle="Cuentas por resultado de visita" />
              <div className="p-6 flex flex-col md:flex-row items-center gap-6">
                <DonutChart
                  slices={Object.entries(STATUS_LABELS).map(([k, v]) => ({ value: m.statusCounts[k] || 0, color: STATUS_COLORS[k], label: v }))}
                  size={210} thickness={36} centerLabel="AVANCE" centerValue={`${m.avancePct}%`} centerSub={`${m.gestionados} gestionados`}
                />
                <div className="space-y-2.5 flex-1">
                  {Object.entries(STATUS_LABELS).map(([k, v]) => {
                    const count = m.statusCounts[k] || 0;
                    const pct = m.total > 0 ? Math.round((count / m.total) * 100) : 0;
                    return (
                      <div key={k} className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: STATUS_COLORS[k] }} />
                        <span className="text-sm text-gray-600 flex-1">{v}</span>
                        <span className="text-sm font-bold text-gray-900 tabular-nums">{count}</span>
                        <span className="text-xs text-gray-400 w-10 text-right">{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>
            <Card>
              <CardHeader icon={<DollarSign size={16} className="text-indigo-500" />} title="Cobertura de Deuda" subtitle="Deuda gestionada vs sin gestionar" />
              <div className="p-6 flex flex-col md:flex-row items-center gap-6">
                <DonutChart
                  slices={[
                    { value: m.deudaGestionada, color: '#6366F1', label: 'Gestionada' },
                    { value: m.deudaTotal - m.deudaGestionada, color: '#E2E8F0', label: 'Sin gestionar' },
                  ]}
                  size={210} thickness={36} centerLabel="RECUPERADO" centerValue={`${Math.round(m.recoveryRate)}%`}
                />
                <div className="space-y-4 flex-1">
                  {[
                    { label: 'Deuda Asignada', value: m.deudaTotal, color: '#1E293B' },
                    { label: 'Deuda Gestionada', value: m.deudaGestionada, color: '#6366F1' },
                    { label: 'Deuda Pendiente', value: m.deudaPendiente, color: '#F59E0B' },
                    { label: 'Recuperado', value: m.deudaTotal - m.deudaPendiente, color: '#22C55E' },
                  ].map(d => (
                    <div key={d.label} className="flex justify-between text-sm">
                      <span className="text-gray-500">{d.label}</span>
                      <span className="font-bold" style={{ color: d.color }}>S/ {d.value.toLocaleString('es-PE', { minimumFractionDigits: 2 })}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          </div>
          <Card>
            <CardHeader icon={<Filter size={16} className="text-indigo-500" />} title="Embudo de Gestión" subtitle="Flujo de conversión desde asignación hasta compromiso" />
            <div className="p-6 flex justify-center">
              <div className="w-full max-w-md">
                <FunnelChart stages={m.funnel} height={200} />
              </div>
            </div>
          </Card>
          <Card>
            <CardHeader icon={<BarChart3 size={16} className="text-indigo-500" />} title="Avance por Sección" subtitle="Distribución de estados en cada sección" />
            <div className="p-6 space-y-4">
              <Legend items={Object.entries(STATUS_LABELS).map(([k, v]) => ({ color: STATUS_COLORS[k], label: v }))} />
              {sections.map(s => (
                <StackedBar key={s.seccion} label={`Sección ${s.seccion}`} total={s.total}
                  segments={Object.entries(STATUS_LABELS).map(([k]) => ({ value: s[k] || 0, color: STATUS_COLORS[k] }))}
                />
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* TAB: DEBT ANALYSIS */}
      {activeTab === 'debt' && (
        <div className="space-y-6">
          <Card>
            <CardHeader icon={<Clock size={16} className="text-orange-500" />} title="Antigüedad de Deuda (Aging)" subtitle="Distribución por días de atraso" />
            <div className="p-6">
              <div className="grid sm:grid-cols-5 gap-3 mb-6">
                {m.aging.map(a => (
                  <div key={a.label} className="rounded-xl p-3 border" style={{ borderColor: a.color + '40', backgroundColor: a.color + '08' }}>
                    <p className="text-xs font-semibold" style={{ color: a.color }}>{a.label}</p>
                    <p className="text-xl font-bold text-gray-900 mt-1">{a.count}</p>
                    <p className="text-xs text-gray-500 mt-0.5">S/ {(a.deuda / 1000).toFixed(0)}K</p>
                  </div>
                ))}
              </div>
              <div className="h-2 rounded-full flex overflow-hidden">
                {m.aging.map(a => (
                  <div key={a.label} style={{ width: `${m.total > 0 ? (a.count / m.total) * 100 : 0}%`, backgroundColor: a.color }} title={`${a.label}: ${a.count}`} />
                ))}
              </div>
              <div className="mt-2">
                <Legend items={m.aging.map(a => ({ color: a.color, label: a.label }))} />
              </div>
            </div>
          </Card>
          <Card>
            <CardHeader icon={<BarChart3 size={16} className="text-indigo-500" />} title="Deuda por Sección" subtitle="Comparativa de deuda asignada entre secciones" />
            <div className="p-6">
              <BarChartVertical
                bars={sections.map(s => ({
                  label: s.seccion,
                  value: Math.round(s.deuda / 1000),
                  color: s.avancePct >= 70 ? '#22C55E' : s.avancePct >= 40 ? '#F59E0B' : '#EF4444',
                }))}
                height={200}
              />
              <p className="text-xs text-gray-400 text-center mt-2">Deuda en miles (S/ K)</p>
            </div>
          </Card>
          {m.segments.length > 0 && (
            <Card>
              <CardHeader icon={<ShieldAlert size={16} className="text-violet-500" />} title="Segmentación de Cartera" subtitle="Deuda por segmento de riesgo" />
              <div className="p-6 space-y-3">
                {m.segments.map((s, i) => {
                  const maxDeuda = m.segments[0].deuda || 1;
                  const pct = (s.deuda / maxDeuda) * 100;
                  return (
                    <div key={s.label} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium text-gray-700">{s.label}</span>
                        <span className="text-gray-500">{s.count} ctas · <span className="font-bold text-gray-900">S/ {s.deuda.toLocaleString('es-PE', { maximumFractionDigits: 0 })}</span></span>
                      </div>
                      <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: PALETTE[i % PALETTE.length] }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
          <Card>
            <CardHeader icon={<Zap size={16} className="text-amber-500" />} title="Top 20 Mayores Deudores" subtitle="Concentración de deuda (Principio de Pareto)" />
            <div className="p-6">
              {(() => {
                const top20Debt = m.topDebtors.reduce((s, c) => s + (parseFloat(c.importe_deuda_asignada) || 0), 0);
                const pctOfTotal = m.deudaTotal > 0 ? Math.round((top20Debt / m.deudaTotal) * 100) : 0;
                return (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
                    <p className="text-sm text-amber-800">
                      <span className="font-bold">{pctOfTotal}%</span> de la deuda total en los <span className="font-bold">20 mayores deudores</span> (S/ {top20Debt.toLocaleString('es-PE', { maximumFractionDigits: 0 })} de S/ {m.deudaTotal.toLocaleString('es-PE', { maximumFractionDigits: 0 })})
                    </p>
                  </div>
                );
              })()}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50/60">
                      {['#', 'Cliente', 'DNI', 'Distrito', 'Deuda Asignada', 'Días Atraso', 'Estado'].map(h => (
                        <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {m.topDebtors.map((c, idx) => (
                      <tr key={c.id} className="hover:bg-indigo-50/30 transition-colors">
                        <td className="px-3 py-2 text-xs font-bold text-gray-400">{idx + 1}</td>
                        <td className="px-3 py-2 font-semibold text-gray-900 truncate max-w-[180px]">{c.nombre_completo || '—'}</td>
                        <td className="px-3 py-2 text-gray-500">{c.numero_documento || '—'}</td>
                        <td className="px-3 py-2 text-gray-500">{c.distrito || '—'}</td>
                        <td className="px-3 py-2 font-bold text-gray-900 whitespace-nowrap">S/ {(parseFloat(c.importe_deuda_asignada) || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}</td>
                        <td className="px-3 py-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${(parseInt(c.dias_atraso) || 0) > 90 ? 'bg-red-100 text-red-700' : (parseInt(c.dias_atraso) || 0) > 60 ? 'bg-orange-100 text-orange-700' : (parseInt(c.dias_atraso) || 0) > 30 ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>
                            {c.dias_atraso || 0}d
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: (STATUS_COLORS[c.estado_gestion] || '#94A3B8') + '20', color: STATUS_COLORS[c.estado_gestion] || '#94A3B8' }}>
                            {STATUS_LABELS[c.estado_gestion] || 'Pendiente'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* TAB: TERRITORY */}
      {activeTab === 'territory' && (
        <div className="space-y-6">
          <Card>
            <CardHeader icon={<MapPin size={16} className="text-violet-500" />} title="Mapa de Concentración por Departamento" subtitle="Tamaño proporcional al número de cuentas" />
            <div className="p-6">
              <TreeMap items={m.departments.slice(0, 12)} width={700} height={280} colorScale={(i) => PALETTE[i % PALETTE.length]} />
            </div>
          </Card>
          <Card>
            <CardHeader icon={<MapPin size={16} className="text-emerald-500" />} title="Top 15 Distritos por Deuda" subtitle="Concentración territorial de deuda" />
            <div className="p-6">
              <BarChartVertical
                bars={m.districts.map((d, i) => ({ label: d.label, value: Math.round(d.deuda / 1000), color: PALETTE[i % PALETTE.length] }))}
                height={220}
              />
              <p className="text-xs text-gray-400 text-center mt-2">Deuda en miles (S/ K)</p>
            </div>
          </Card>
          <Card>
            <CardHeader icon={<BarChart3 size={16} className="text-indigo-500" />} title="Detalle por Sección" />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/60">
                    {['Sección', 'Clientes', 'Pendientes', 'Habidos', 'No Habidos', 'Inubic.', 'GPS', 'Deuda', 'Avance'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sections.map(s => (
                    <tr key={s.seccion} className="hover:bg-indigo-50/30 transition-colors">
                      <td className="px-4 py-3"><span className="inline-flex items-center justify-center w-8 h-8 bg-indigo-100 text-indigo-700 rounded-lg font-bold text-sm">{s.seccion}</span></td>
                      <td className="px-4 py-3 font-semibold text-gray-900">{s.total}</td>
                      <td className="px-4 py-3 text-gray-600">{s.pendiente}</td>
                      <td className="px-4 py-3 text-emerald-600 font-medium">{s.visitado_habido}</td>
                      <td className="px-4 py-3 text-amber-600 font-medium">{s.visitado_no_habido}</td>
                      <td className="px-4 py-3 text-red-500 font-medium">{s.fallecido_inubicable}</td>
                      <td className="px-4 py-3"><span className="text-teal-600 font-medium">{s.geolocated}</span><span className="text-gray-400 text-xs">/{s.total}</span></td>
                      <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">S/ {s.deuda.toLocaleString('es-PE', { maximumFractionDigits: 0 })}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${s.avancePct}%`, backgroundColor: s.avancePct >= 70 ? '#22C55E' : s.avancePct >= 40 ? '#F59E0B' : '#EF4444' }} />
                          </div>
                          <span className="text-xs font-bold text-gray-700">{s.avancePct}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* TAB: PERFORMANCE */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          {m.contactResults.length > 0 && (
            <Card>
              <CardHeader icon={<Target size={16} className="text-indigo-500" />} title="Resultados de Contacto (Nivel 1)" subtitle="Distribución de tipos de contacto" />
              <div className="p-6">
                <BarChartVertical bars={m.contactResults.map((r, i) => ({ label: r.label, value: r.value, color: PALETTE[i % PALETTE.length] }))} height={200} />
              </div>
            </Card>
          )}
          {m.channels.length > 0 && (
            <Card>
              <CardHeader icon={<Zap size={16} className="text-teal-500" />} title="Canal de Gestión" subtitle="Distribución de visitas por canal" />
              <div className="p-6 flex flex-col md:flex-row items-center gap-6">
                <DonutChart
                  slices={m.channels.map((c, i) => ({ value: c.value, color: PALETTE[i % PALETTE.length], label: c.label }))}
                  size={180} thickness={30} centerValue={m.channels.reduce((s, c) => s + c.value, 0)} centerLabel="TOTAL"
                />
                <div className="space-y-2 flex-1">
                  {m.channels.map((c, i) => (
                    <div key={c.label} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: PALETTE[i % PALETTE.length] }} />
                      <span className="text-sm text-gray-600 flex-1">{c.label}</span>
                      <span className="text-sm font-bold text-gray-900">{c.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
          {m.withPromise.length > 0 && (
            <Card>
              <CardHeader icon={<DollarSign size={16} className="text-emerald-500" />} title="Promesas de Pago" subtitle="Compromisos registrados de clientes" />
              <div className="p-6">
                <div className="grid sm:grid-cols-3 gap-4">
                  <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-100">
                    <p className="text-xs font-semibold text-emerald-600 uppercase">Promesas</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{m.withPromise.length}</p>
                  </div>
                  <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-100">
                    <p className="text-xs font-semibold text-emerald-600 uppercase">Monto Prometido</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">S/ {m.promiseAmount.toLocaleString('es-PE', { maximumFractionDigits: 0 })}</p>
                  </div>
                  <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-100">
                    <p className="text-xs font-semibold text-emerald-600 uppercase">Prom. por Cuenta</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">S/ {m.withPromise.length > 0 ? (m.promiseAmount / m.withPromise.length).toLocaleString('es-PE', { maximumFractionDigits: 0 }) : 0}</p>
                  </div>
                </div>
              </div>
            </Card>
          )}
          {m.contactResults.length === 0 && m.channels.length === 0 && m.withPromise.length === 0 && (
            <Card className="p-12 text-center">
              <Target size={36} className="text-gray-300 mx-auto mb-3" />
              <p className="text-gray-600 font-semibold">Aún no hay datos de rendimiento</p>
              <p className="text-sm text-gray-400 mt-1">Los datos aparecerán cuando los gestores registren resultados.</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
