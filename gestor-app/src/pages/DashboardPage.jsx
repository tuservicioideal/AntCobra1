import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { collection, getDocs, doc, setDoc, getDoc } from 'firebase/firestore';
import { db } from '../services/firebase';
import { getActiveCampaignId } from '../services/campaignUtils';
import { useOnlineStatus } from '../hooks/useOnlineStatus';
import {
  Users, DollarSign, Clock, MapPin, ChevronRight, Search,
  FileDown, TrendingUp, CheckCircle2, AlertTriangle, Eye, Loader2, RefreshCw,
  FolderOpen, Info, Flame, ShieldAlert, CreditCard, Wifi, WifiOff, Calendar, Images
} from 'lucide-react';
import ClientDetailModal from '../components/ClientDetailModal';
import { downloadLetters } from '../services/letterGenerator';
import { getEstructuraTerritorial } from '../services/catalogService';
import { downloadLettersJpgForClients } from '../services/letterJpgBulkService';

const HIGH_VALUE_THRESHOLD = 500;
const EMPTY_SECTIONS = [];          // stable reference — avoids [] !== [] on every render

export default function DashboardPage({ user, userData }) {
  const isAdmin = userData?.rol === 'admin' || userData?.rol === 'supervisor';
  const isAsistente = userData?.rol === 'asistente';
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedClient, setSelectedClient] = useState(null);
  const [filter, setFilter] = useState('all');
  const [downloading, setDownloading] = useState(false);
  const [downloadingJpg, setDownloadingJpg] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedClients, setSelectedClients] = useState(new Set());
  const [stats, setStats] = useState({
    total: 0,
    pendiente: 0,
    visitado: 0,
    deudaTotal: 0,
    deudaPendiente: 0,
    gestores: 0,
    secciones: 0,
    cartasEntregadas: 0,
  });
  const [tramoInfo, setTramoInfo] = useState(null); // { dia_actual, ... }
  const { isOnline } = useOnlineStatus();

  // Section discovery state — if profile has no section, we discover available ones
  const [availableSections, setAvailableSections] = useState([]);
  const [catalog, setCatalog] = useState({});  // territorial catalog: region→zona→secciones
  const [manualSection, setManualSection] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(14);

  // Multi-section support: secciones array (composite keys) takes priority
  const gestorSecciones = userData?.secciones ?? EMPTY_SECTIONS;
  const gestorSeccion = userData?.seccion || manualSection || '';
  // String key derived from sections — primitive comparison avoids referential loops
  const sectionsKey = gestorSecciones.join(',');
  const gestorName = userData?.nombre || user?.displayName || user?.email || '';

  const resolveDni = useCallback((clientData) => {
    const rawDni = clientData?.numero_documento
      || clientData?.dni
      || clientData?.nro_documento
      || clientData?.documento
      || '';
    return String(rawDni).trim();
  }, []);

  // ── Discover available sections from campaigns + catalog ──
  const discoverSections = useCallback(async () => {
    setDiscovering(true);
    try {
      const [campaignId, cat] = await Promise.all([
        getActiveCampaignId(),
        getEstructuraTerritorial(),
      ]);
      setCatalog(cat);
      if (!campaignId) { setAvailableSections([]); return; }
      const gestoresSnap = await getDocs(
        collection(db, 'campañas', campaignId, 'gestores')
      );
      const sectionSet = new Set();
      gestoresSnap.forEach((g) => sectionSet.add(g.id));
      setAvailableSections([...sectionSet].sort());
    } catch (err) {
      console.error('Error discovering sections:', err);
    } finally {
      setDiscovering(false);
    }
  }, []);

  // ── Load clients for all assigned sections ──
  const loadingRef = useRef(false);
  const loadClients = useCallback(async () => {
    if (loadingRef.current) return;           // prevent concurrent / re-entrant calls
    loadingRef.current = true;
    // Need at least one section (from secciones array or legacy seccion)
    const sectionsToLoad = sectionsKey
      ? sectionsKey.split(',')
      : (gestorSeccion ? [gestorSeccion] : []);

    if (sectionsToLoad.length === 0) {
      setLoading(false);
      loadingRef.current = false;
      discoverSections();
      return;
    }
    try {
      setLoading(true);
      const campaignId = await getActiveCampaignId();
      if (!campaignId) { setClients([]); setLoading(false); return; }

      if (isAdmin) {
        const gestoresSnap = await getDocs(collection(db, 'campañas', campaignId, 'gestores'));
        const allClients = [];
        const uniqueClientes = new Map();

        for (const gestorDoc of gestoresSnap.docs) {
          const secId = gestorDoc.id;
          const clientsRef = collection(db, 'campañas', campaignId, 'gestores', secId, 'clientes');
          const clientsSnap = await getDocs(clientsRef);
          clientsSnap.forEach((d) => {
            const rawData = d.data();
            const dni = resolveDni(rawData);
            const data = {
              id: d.id,
              campaignId,
              seccion_key: secId,
              ...rawData,
              numero_documento: dni || rawData.numero_documento || '',
            };
            const key = data.numero_documento || `${secId}_${d.id}`;
            const existing = uniqueClientes.get(key);
            if (!existing || (data.estado_gestion && data.estado_gestion !== 'pendiente')) {
              uniqueClientes.set(key, data);
            }
          });
        }

        allClients.push(...uniqueClientes.values());
        setClients(allClients);

        const total = allClients.length;
        const pendiente = allClients.filter(c => (c.estado_gestion || 'pendiente') === 'pendiente').length;
        const visitado = total - pendiente;
        const deudaTotal = allClients.reduce((sum, c) => sum + (parseFloat(c.importe_deuda_asignada) || 0), 0);
        const deudaPendiente = allClients.reduce((sum, c) => sum + (parseFloat(c.importe_deuda_pendiente) || 0), 0);
        const cartasEntregadas = allClients.filter(c => (c.estado_gestion || 'pendiente') !== 'pendiente').length;

        setStats({
          total,
          pendiente,
          visitado,
          deudaTotal,
          deudaPendiente,
          gestores: gestoresSnap.size,
          secciones: gestoresSnap.size,
          cartasEntregadas,
        });
        return;
      }

      // Load tramo info from campaign metadata
      try {
        const campaignDoc = await getDoc(doc(db, 'campañas', campaignId));
        if (campaignDoc.exists()) {
          const campData = campaignDoc.data();
          setTramoInfo(campData.tramo_info || null);
        }
      } catch (e) {
        console.warn('Could not load tramo info:', e);
      }

      // Deduplicate by numero_documento (DNI) as primary key,
      // falling back to doc id (codigo_cliente)
      const clientMap = new Map();

      const loadFromSection = async (secId) => {
        const clientsRef = collection(
          db, 'campañas', campaignId, 'gestores', secId, 'clientes'
        );
        const clientsSnap = await getDocs(clientsRef);
        clientsSnap.forEach((d) => {
          const rawData = d.data();
          const dni = resolveDni(rawData);
          const data = {
            id: d.id,
            campaignId,
            ...rawData,
            numero_documento: dni || rawData.numero_documento || '',
          };
          // Use DNI as dedup key (most reliable unique identifier)
          const key = data.numero_documento || d.id;
          const existing = clientMap.get(key);
          // Keep version with visit data if available
          if (!existing
              || (data.estado_gestion && data.estado_gestion !== 'pendiente')) {
            clientMap.set(key, data);
          }
        });
      };

      // Load from all assigned sections (composite keys)
      for (const secId of sectionsToLoad) {
        await loadFromSection(secId);
      }

      // If no clients found and we only used a legacy single section,
      // try case-insensitive match as fallback
      if (clientMap.size === 0 && gestorSecciones.length === 0 && gestorSeccion) {
        const gestoresSnap = await getDocs(
          collection(db, 'campañas', campaignId, 'gestores')
        );
        for (const gestorDoc of gestoresSnap.docs) {
          if (gestorDoc.id.toLowerCase() === gestorSeccion.toLowerCase()
              && gestorDoc.id !== gestorSeccion) {
            await loadFromSection(gestorDoc.id);
            break;
          }
        }
      }

      const allClients = [...clientMap.values()];
      setClients(allClients);
      const total = allClients.length;
      const pendiente = allClients.filter(c => c.estado_gestion === 'pendiente').length;
      const visitado = total - pendiente;
      const deudaTotal = allClients.reduce((sum, c) => sum + (parseFloat(c.importe_deuda_asignada) || 0), 0);
      const deudaPendiente = allClients.reduce((sum, c) => sum + (parseFloat(c.importe_deuda_pendiente) || 0), 0);
      setStats({
        total,
        pendiente,
        visitado,
        deudaTotal,
        deudaPendiente,
        gestores: 0,
        secciones: sectionsToLoad.length,
        cartasEntregadas: visitado,
      });
    } catch (err) {
      console.error('Error loading clients:', err);
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, [gestorSeccion, sectionsKey, discoverSections, gestorSecciones.length, isAdmin, resolveDni]);

  useEffect(() => { loadClients(); }, [loadClients]);

  const handleRefresh = async () => { setRefreshing(true); await loadClients(); setRefreshing(false); };

  // Handle manual section selection (composite keys like "01_1211_H")
  const handleSelectSection = async (sec) => {
    setManualSection(sec);
    // Save as secciones array + legacy seccion field
    if (user?.uid) {
      try {
        const parts = sec.split('_');
        const letra = parts.length >= 3 ? parts[parts.length - 1] : sec;
        await setDoc(doc(db, 'usuarios', user.uid), {
          secciones: [sec],
          seccion: letra,
        }, { merge: true });
      } catch (e) {
        console.warn('Could not update section in profile:', e);
      }
    }
  };

  const filteredClients = clients.filter(c => {
    if (filter === 'pendiente' && c.estado_gestion !== 'pendiente') return false;
    if (filter === 'visitado' && c.estado_gestion === 'pendiente') return false;
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      (c.nombre_completo || '').toLowerCase().includes(term) ||
      (c.numero_documento || '').includes(term) ||
      (c.distrito || '').toLowerCase().includes(term) ||
      (c.direccion || '').toLowerCase().includes(term) ||
      (isAdmin && (c.seccion_key || '').toLowerCase().includes(term))
    );
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [search, filter, clients.length]);

  useEffect(() => {
    setSelectedClients(new Set());
  }, [search, filter, clients.length, currentPage]);

  const totalPages = Math.max(1, Math.ceil(filteredClients.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const paginatedClients = filteredClients.slice(startIndex, endIndex);

  const adminInsights = useMemo(() => {
    if (!isAdmin) return null;
    const total = clients.length || 1;
    const byStatus = {
      pendiente: 0,
      visitado_habido: 0,
      visitado_no_habido: 0,
      fallecido_inubicable: 0,
      suplantacion: 0,
      pago_no_registrado: 0,
    };
    const sectionMap = {};
    let criticalDebtCount = 0;
    let criticalAgingCount = 0;

    clients.forEach((c) => {
      const status = c.estado_gestion || 'pendiente';
      byStatus[status] = (byStatus[status] || 0) + 1;
      const sec = c.seccion_key || 'sin_seccion';
      if (!sectionMap[sec]) {
        sectionMap[sec] = { key: sec, total: 0, deuda: 0, gestionados: 0 };
      }
      sectionMap[sec].total += 1;
      sectionMap[sec].deuda += parseFloat(c.importe_deuda_asignada) || 0;
      if ((c.estado_gestion || 'pendiente') !== 'pendiente') sectionMap[sec].gestionados += 1;

      if ((parseFloat(c.importe_deuda_asignada) || 0) >= 500) criticalDebtCount += 1;
      if ((parseInt(c.dias_atraso, 10) || 0) >= 90) criticalAgingCount += 1;
    });

    const statusRows = [
      { key: 'pendiente', label: 'Pendientes', color: 'bg-gray-400' },
      { key: 'visitado_habido', label: 'Habidos', color: 'bg-emerald-500' },
      { key: 'visitado_no_habido', label: 'No Habidos', color: 'bg-amber-500' },
      { key: 'fallecido_inubicable', label: 'Inubicables', color: 'bg-red-500' },
      { key: 'suplantacion', label: 'Suplantación', color: 'bg-rose-500' },
      { key: 'pago_no_registrado', label: 'Pago no registrado', color: 'bg-blue-500' },
    ].map((r) => {
      const value = byStatus[r.key] || 0;
      const pct = Math.round((value / total) * 100);
      return { ...r, value, pct };
    });

    const topSectionsByClients = Object.values(sectionMap)
      .sort((a, b) => b.total - a.total)
      .slice(0, 6)
      .map((s) => ({
        ...s,
        avancePct: s.total > 0 ? Math.round((s.gestionados / s.total) * 100) : 0,
      }));

    const topSectionsByDebt = Object.values(sectionMap)
      .sort((a, b) => b.deuda - a.deuda)
      .slice(0, 6);

    const topDebtors = [...clients]
      .sort((a, b) => (parseFloat(b.importe_deuda_asignada) || 0) - (parseFloat(a.importe_deuda_asignada) || 0))
      .slice(0, 5);

    return {
      statusRows,
      topSectionsByClients,
      topSectionsByDebt,
      topDebtors,
      criticalDebtCount,
      criticalAgingCount,
    };
  }, [clients, isAdmin]);

  const handleDownloadLetters = async () => {
    setDownloading(true);
    try {
      const count = await downloadLetters(clients, gestorSeccion, gestorName);
      alert(`✓ Se descargaron ${count} cartas de cobranza`);
    } catch (err) { alert('Error al generar cartas: ' + err.message); }
    finally { setDownloading(false); }
  };

  const toggleClientSelection = (clientKey) => {
    setSelectedClients((prev) => {
      const next = new Set(prev);
      if (next.has(clientKey)) next.delete(clientKey);
      else next.add(clientKey);
      return next;
    });
  };

  const handleSelectPage = () => {
    const pageKeys = paginatedClients.map((c) => `${c.campaignId}-${c.id}`);
    setSelectedClients((prev) => {
      const next = new Set(prev);
      const allSelected = pageKeys.every((k) => next.has(k));
      pageKeys.forEach((k) => {
        if (allSelected) next.delete(k);
        else next.add(k);
      });
      return next;
    });
  };

  const handleDownloadJpg = async (mode) => {
    const selected = clients.filter((c) => selectedClients.has(`${c.campaignId}-${c.id}`));
    const targets = mode === 'selected' ? selected : filteredClients;
    if (!targets.length) {
      alert(mode === 'selected'
        ? 'Selecciona uno o más clientes primero.'
        : 'No hay clientes visibles para descargar.');
      return;
    }
    setDownloadingJpg(true);
    try {
      const count = await downloadLettersJpgForClients(targets, gestorName);
      alert(`Se descargaron ${count} cartas JPG.`);
    } catch (err) {
      alert(`Error al descargar cartas JPG: ${err.message}`);
    } finally {
      setDownloadingJpg(false);
    }
  };

  const getStatusConfig = (status) => {
    switch (status) {
      case 'visitado_habido':
        return { label: 'Habido', cls: 'bg-emerald-50 text-emerald-700', icon: <CheckCircle2 size={12} /> };
      case 'visitado_no_habido':
        return { label: 'No Habido', cls: 'bg-amber-50 text-amber-700', icon: <Eye size={12} /> };
      case 'fallecido_inubicable':
        return { label: 'Inubicable', cls: 'bg-red-50 text-red-600', icon: <AlertTriangle size={12} /> };
      case 'suplantacion':
        return { label: 'Suplantación', cls: 'bg-rose-100 text-rose-700', icon: <ShieldAlert size={12} /> };
      case 'pago_no_registrado':
        return { label: 'Pago No Reg.', cls: 'bg-blue-50 text-blue-700', icon: <CreditCard size={12} /> };
      default:
        return { label: 'Pendiente', cls: 'bg-gray-100 text-gray-600', icon: <Clock size={12} /> };
    }
  };

  const progressPercent = stats.total > 0 ? Math.round((stats.visitado / stats.total) * 100) : 0;

  // ── Section Selector (when no section is assigned) ──
  if (!isAdmin && !gestorSeccion && gestorSecciones.length === 0 && !loading) {
    return (
      <div className="p-4 sm:p-6 lg:p-8">
        <div className="max-w-lg mx-auto mt-8">
          <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
            <div className="w-16 h-16 bg-amber-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <FolderOpen size={28} className="text-amber-500" />
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Sección no asignada</h2>
            <p className="text-sm text-gray-500 mb-6">
              Tu perfil aún no tiene una sección asignada. Contacta al administrador o selecciona tu sección manualmente:
            </p>

            {discovering ? (
              <div className="flex items-center justify-center gap-2 py-4">
                <Loader2 size={18} className="animate-spin text-indigo-500" />
                <span className="text-sm text-gray-500">Buscando secciones disponibles...</span>
              </div>
            ) : availableSections.length > 0 ? (
              <div className="space-y-3">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Secciones disponibles en campañas
                </p>
                {/* Hierarchical display when catalog is available */}
                {Object.keys(catalog).length > 0 ? (
                  <div className="space-y-4 text-left">
                    {Object.entries(catalog).sort(([a],[b]) => a.localeCompare(b)).map(([regionKey, regionData]) => {
                      const zonas = regionData?.zonas ?? {};
                      // Only show regions that have available sections
                      const regionSections = availableSections.filter(s => s.startsWith(regionKey + '_'));
                      if (regionSections.length === 0) return null;
                      return (
                        <div key={regionKey} className="border border-indigo-100 rounded-lg overflow-hidden">
                          <div className="bg-indigo-50 px-3 py-2">
                            <span className="text-sm font-bold text-indigo-700">Región {regionKey}</span>
                            <span className="ml-2 text-xs text-indigo-400">{regionSections.length} secciones</span>
                          </div>
                          {Object.entries(zonas).sort(([a],[b]) => a.localeCompare(b)).map(([zonaKey, zonaData]) => {
                            const secs = (zonaData?.secciones ?? []).filter(s =>
                              availableSections.includes(`${regionKey}_${zonaKey}_${s}`)
                            );
                            if (secs.length === 0) return null;
                            return (
                              <div key={zonaKey} className="border-t border-indigo-50 px-3 py-2">
                                <p className="text-xs font-semibold text-teal-600 mb-1.5">Zona {zonaKey}</p>
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                                  {secs.sort().map(letra => {
                                    const compositeKey = `${regionKey}_${zonaKey}_${letra}`;
                                    return (
                                      <button
                                        key={compositeKey}
                                        onClick={() => handleSelectSection(compositeKey)}
                                        className="flex flex-col items-start gap-0.5 px-3 py-2 bg-white text-indigo-700
                                                 rounded-lg hover:bg-indigo-100 transition-all text-left border border-indigo-200"
                                        title={compositeKey}
                                      >
                                        <span className="text-sm font-bold">Sección {letra}</span>
                                        <span className="text-[10px] text-indigo-400">R{regionKey} · Z{zonaKey}</span>
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* Fallback flat grid when no catalog */
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {availableSections.map((sec) => {
                      const parts = sec.split('_');
                      const hasComposite = parts.length === 3;
                      const region = hasComposite ? parts[0] : '';
                      const zona = hasComposite ? parts[1] : '';
                      const letra = hasComposite ? parts[2] : sec;
                      return (
                      <button
                        key={sec}
                        onClick={() => handleSelectSection(sec)}
                        className="flex flex-col items-start gap-0.5 px-3 py-3 bg-indigo-50 text-indigo-700
                                 rounded-lg hover:bg-indigo-100 transition-all text-left border border-indigo-200"
                        title={sec}
                      >
                        <span className="text-base font-bold">Sección {letra}</span>
                        {hasComposite && (
                          <span className="text-[11px] text-indigo-400 font-medium">R{region} · Z{zona}</span>
                        )}
                      </button>
                      );
                    })}
                  </div>
                )}
                <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <Info size={16} className="text-blue-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-blue-700">
                      Al seleccionar una sección, se guardará en tu perfil y podrás ver los clientes asignados.
                      Pide al administrador confirmar cuál es tu sección.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-4">
                <p className="text-sm text-gray-500">
                  No se encontraron campañas activas. El administrador debe distribuir la cartera primero.
                </p>
                <button
                  onClick={discoverSections}
                  className="mt-3 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-indigo-700
                           bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-all"
                >
                  <RefreshCw size={14} />
                  Reintentar
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-0">
      <div className="max-w-7xl mx-auto">
      {/* Online/Offline indicator */}
      {!isOnline && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3
                      flex items-center gap-2.5 animate-pulse">
          <WifiOff size={18} className="text-amber-500 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-amber-700">Modo sin conexión</p>
            <p className="text-xs text-amber-600">Los datos se sincronizarán automáticamente al recuperar señal.</p>
          </div>
        </div>
      )}

      {/* Tramo info bar */}
      {tramoInfo && tramoInfo.dia_actual > 0 && (
        <div className="mb-4 bg-gradient-to-r from-indigo-50 to-violet-50 border border-indigo-200
                      rounded-xl px-4 py-3 flex items-center gap-3">
          <Calendar size={18} className="text-indigo-500 shrink-0" />
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold text-indigo-800">
                Día {tramoInfo.dia_actual} de 60
              </span>
              <span className="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-0.5 rounded-full font-bold">
                Tramo {tramoInfo.dia_actual <= 8 ? 1 : tramoInfo.dia_actual <= 43 ? 2 : 3}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 bg-indigo-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all"
                style={{ width: `${Math.min(100, Math.round((tramoInfo.dia_actual / 60) * 100))}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Page title row */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5 flex items-center gap-2">
            {gestorSeccion
              ? `Resumen de tu cartera — Sección ${gestorSeccion}`
              : isAdmin
                ? 'Resumen general de la empresa'
                : 'Esperando asignación de sección'}
            {isOnline
              ? <span className="inline-flex items-center gap-1 text-[10px] bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full font-medium"><Wifi size={10} /> En línea</span>
              : <span className="inline-flex items-center gap-1 text-[10px] bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full font-medium"><WifiOff size={10} /> Offline</span>
            }
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-gray-700
                     bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-all disabled:opacity-50"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            Actualizar
          </button>
          {clients.length > 0 && (
            <>
              <button
                onClick={handleDownloadLetters}
                disabled={downloading}
                className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-white
                         bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-all disabled:opacity-50"
              >
                {downloading ? <Loader2 size={16} className="animate-spin" /> : <FileDown size={16} />}
                {downloading ? 'Generando...' : 'Descargar Cartas'}
              </button>
              <button
                onClick={() => handleDownloadJpg('visible')}
                disabled={downloadingJpg}
                className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-white
                         bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-all disabled:opacity-50"
              >
                {downloadingJpg ? <Loader2 size={16} className="animate-spin" /> : <Images size={16} />}
                {downloadingJpg ? 'Procesando JPG...' : 'JPG visibles'}
              </button>
              <button
                onClick={() => handleDownloadJpg('selected')}
                disabled={downloadingJpg}
                className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-emerald-700
                         bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-all disabled:opacity-50"
              >
                {downloadingJpg ? <Loader2 size={16} className="animate-spin" /> : <Images size={16} />}
                JPG seleccionados ({selectedClients.size})
              </button>
            </>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className={`grid gap-4 mb-6 ${
        isAdmin
          ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-4'
          : isAsistente
            ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3'
            : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-5'
      }`}>
        <StatCard icon={<Users size={20} />} label="Total Cuentas" value={stats.total} color="indigo" />
        <StatCard icon={<Clock size={20} />} label="Pendientes" value={stats.pendiente} color="amber" />
        <StatCard icon={<TrendingUp size={20} />} label="Visitados" value={stats.visitado} color="emerald" />
        {isAdmin && (
          <StatCard icon={<FileDown size={20} />} label="Cartas Entregadas" value={stats.cartasEntregadas} color="orange" />
        )}
        {isAdmin && (
          <StatCard icon={<Users size={20} />} label="Gestores Activos" value={stats.gestores} color="rose" />
        )}
        {isAdmin && (
          <StatCard icon={<MapPin size={20} />} label="Secciones con Cartera" value={stats.secciones} color="indigo" />
        )}
        {!isAsistente && (
          <>
            <StatCard
              icon={<DollarSign size={20} />}
              label="Deuda Asig."
              value={`S/ ${stats.deudaTotal.toLocaleString('es-PE', { minimumFractionDigits: 2 })}`}
              color="rose"
              small
            />
            <StatCard
              icon={<DollarSign size={20} />}
              label="Deuda Pend."
              value={`S/ ${(stats.deudaPendiente || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`}
              color="orange"
              small
            />
          </>
        )}
      </div>

      {isAdmin && adminInsights && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-6">
          <div className="xl:col-span-2 bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 mb-3">Estado global de gestión</h3>
            <div className="space-y-3">
              {adminInsights.statusRows.map((row) => (
                <div key={row.key}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600">{row.label}</span>
                    <span className="font-semibold text-gray-900">{row.value} ({row.pct}%)</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className={`h-full ${row.color}`} style={{ width: `${row.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 mb-3">Alertas de cartera</h3>
            <div className="space-y-3">
              <div className="p-3 rounded-lg border border-orange-200 bg-orange-50">
                <p className="text-xs uppercase tracking-wide text-orange-700 font-semibold">Deuda alta</p>
                <p className="text-2xl font-bold text-orange-800">{adminInsights.criticalDebtCount}</p>
                <p className="text-xs text-orange-700">Cuentas con deuda {'>='} S/ 500</p>
              </div>
              <div className="p-3 rounded-lg border border-red-200 bg-red-50">
                <p className="text-xs uppercase tracking-wide text-red-700 font-semibold">Atraso crítico</p>
                <p className="text-2xl font-bold text-red-800">{adminInsights.criticalAgingCount}</p>
                <p className="text-xs text-red-700">Cuentas con 90+ días de atraso</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {isAdmin && adminInsights && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-6">
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 mb-3">Top secciones por volumen</h3>
            <div className="space-y-3">
              {adminInsights.topSectionsByClients.map((s) => (
                <div key={s.key}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-gray-700">Sección {s.key}</span>
                    <span className="text-gray-500">{s.total} cuentas · {s.avancePct}% avance</span>
                  </div>
                  <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500" style={{ width: `${s.avancePct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 mb-3">Top secciones por deuda</h3>
            <div className="space-y-3">
              {adminInsights.topSectionsByDebt.map((s) => (
                <div key={s.key} className="flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-700">Sección {s.key}</span>
                  <span className="font-semibold text-gray-900">
                    S/ {s.deuda.toLocaleString('es-PE', { minimumFractionDigits: 0 })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Progress bar */}
      {stats.total > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 mb-6 shadow-sm">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-600 font-medium">Avance de gestión</span>
            <span className="text-gray-900 font-semibold">{progressPercent}%</span>
          </div>
          <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-600 rounded-full transition-all duration-700"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {stats.visitado} de {stats.total} clientes gestionados
          </p>
        </div>
      )}

      {/* Filters + Search */}
      <div className="bg-white border border-slate-200 rounded-xl mb-4 shadow-sm overflow-hidden">
        <div className="p-4 flex flex-col xl:flex-row xl:items-center gap-3">
          <div className="flex items-center gap-1.5 bg-gray-100 p-1 rounded-lg">
            {[
              { key: 'all', label: 'Todos', count: stats.total },
              { key: 'pendiente', label: 'Pendientes', count: stats.pendiente },
              { key: 'visitado', label: 'Visitados', count: stats.visitado },
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all
                  ${filter === tab.key
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                  }`}
              >
                {tab.label}
                <span className="ml-1.5 text-xs opacity-60">{tab.count}</span>
              </button>
            ))}
          </div>

          <div className="relative xl:ml-auto w-full xl:max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder={isAdmin ? 'Buscar por nombre, DNI, distrito o sección...' : 'Buscar por nombre, DNI o distrito...'}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-gray-300 bg-white
                       focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none"
            />
          </div>
        </div>

        {/* Client table/list */}
        <div className="border-t border-slate-100">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 size={24} className="text-indigo-500 animate-spin mb-3" />
              <p className="text-sm text-gray-500">Cargando cartera...</p>
            </div>
          ) : filteredClients.length === 0 ? (
            <div className="text-center py-16 px-4">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Users size={24} className="text-gray-400" />
              </div>
              <p className="text-gray-800 font-semibold text-base">
                {search ? 'Sin resultados' : 'No hay cuentas asignadas aún'}
              </p>
              <p className="text-gray-500 text-sm mt-1 max-w-xs mx-auto">
                {search
                  ? 'Intenta con otro término de búsqueda'
                  : isAdmin
                    ? 'No se encontraron clientes en la campaña activa. Distribuye la cartera desde administración.'
                    : `No se encontraron clientes para la sección "${gestorSeccion}". La cartera debe ser distribuida desde la app de administración.`}
              </p>
            </div>
          ) : (
            <>
              {/* Desktop table header */}
              <div className="hidden md:grid grid-cols-[minmax(280px,1fr)_140px_180px_128px_112px_28px] gap-4 px-5 py-3
                            text-xs font-semibold text-gray-500 uppercase tracking-wider bg-slate-50 border-b border-slate-100">
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={paginatedClients.length > 0 && paginatedClients.every((c) => selectedClients.has(`${c.campaignId}-${c.id}`))}
                    onChange={handleSelectPage}
                  />
                  Cliente
                </span>
                <span>DNI</span>
                <span>Ubicación</span>
                <span>Estado</span>
                <span className="text-right">Deuda</span>
                <span />
              </div>

              {/* Client rows */}
              <div className="divide-y divide-gray-100">
                {paginatedClients.map((client) => {
                  const statusCfg = getStatusConfig(client.estado_gestion);
                  const deuda = parseFloat(client.importe_deuda_asignada || 0);
                  const isHighVal = deuda > HIGH_VALUE_THRESHOLD;

                  return (
                    <button
                      key={`${client.campaignId}-${client.id}`}
                      onClick={() => setSelectedClient(client)}
                      className={`w-full text-left px-5 py-4 hover:bg-indigo-50/40 transition-all group
                        ${isHighVal ? 'border-l-4 border-l-orange-400' : ''}`}
                    >
                      {/* Mobile layout */}
                      <div className="flex items-center gap-3 md:hidden">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 text-sm font-semibold
                          ${isHighVal ? 'bg-orange-100 text-orange-700' : 'bg-indigo-100 text-indigo-700'}`}>
                          {isHighVal
                            ? <Flame size={18} />
                            : (client.nombre_completo || '?').charAt(0).toUpperCase()
                          }
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-gray-900 truncate">{client.nombre_completo || 'Sin nombre'}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md font-medium ${statusCfg.cls}`}>
                              {statusCfg.icon} {statusCfg.label}
                            </span>
                            <span className="text-xs text-gray-400">DNI: {client.numero_documento || '—'}</span>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-bold text-gray-900">S/ {deuda.toFixed(2)}</p>
                          <p className="text-[10px] text-gray-400">{client.dias_atraso || 0}d atraso</p>
                        </div>
                        <ChevronRight size={16} className="text-gray-300 group-hover:text-indigo-500 shrink-0" />
                      </div>

                      {/* Desktop layout */}
                      <div className="hidden md:grid grid-cols-[minmax(280px,1fr)_140px_180px_128px_112px_28px] gap-4 items-center">
                        <div className="flex items-center gap-3 min-w-0">
                          <input
                            type="checkbox"
                            checked={selectedClients.has(`${client.campaignId}-${client.id}`)}
                            onChange={(e) => {
                              e.stopPropagation();
                              toggleClientSelection(`${client.campaignId}-${client.id}`);
                            }}
                            onClick={(e) => e.stopPropagation()}
                          />
                          <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-sm font-semibold
                            ${isHighVal ? 'bg-orange-100 text-orange-700' : 'bg-indigo-100 text-indigo-700'}`}>
                            {isHighVal
                              ? <Flame size={16} />
                              : (client.nombre_completo || '?').charAt(0).toUpperCase()
                            }
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-gray-900 truncate">{client.nombre_completo || 'Sin nombre'}</p>
                            <p className="text-xs text-gray-400">{client.dias_atraso || 0} días de atraso</p>
                          </div>
                        </div>
                        <span className="text-sm text-gray-600">{client.numero_documento || '—'}</span>
                        <span className="text-sm text-gray-500 truncate flex items-center gap-1">
                          <MapPin size={12} className="shrink-0 text-gray-400" />
                          {client.distrito || client.departamento || '—'}
                        </span>
                        <span className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md font-medium w-fit ${statusCfg.cls}`}>
                          {statusCfg.icon} {statusCfg.label}
                        </span>
                        <span className="text-sm font-semibold text-gray-900 text-right">S/ {deuda.toFixed(2)}</span>
                        <ChevronRight size={16} className="text-gray-300 group-hover:text-indigo-500" />
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Footer count */}
              <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 text-xs text-gray-500">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <span>
                    Mostrando {filteredClients.length === 0 ? 0 : startIndex + 1}
                    {' - '}
                    {Math.min(endIndex, filteredClients.length)} de {filteredClients.length} clientes
                    {filter !== 'all' && ` · Filtro: ${filter}`}
                  </span>
                  <div className="flex items-center gap-2">
                    <label htmlFor="page-size" className="text-xs text-gray-500">Por página</label>
                    <select
                      id="page-size"
                      value={pageSize}
                      onChange={(e) => setPageSize(parseInt(e.target.value, 10))}
                      className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700"
                    >
                      {[10, 14, 20, 30].map((size) => (
                        <option key={size} value={size}>{size}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={safeCurrentPage <= 1}
                      className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 disabled:opacity-40"
                    >
                      Anterior
                    </button>
                    <span className="text-xs text-gray-600">
                      Página {safeCurrentPage} de {totalPages}
                    </span>
                    <button
                      type="button"
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={safeCurrentPage >= totalPages}
                      className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 disabled:opacity-40"
                    >
                      Siguiente
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      </div>

      {/* Client Detail Modal */}
      {selectedClient && !isAdmin && (
        <ClientDetailModal
          client={selectedClient}
          seccion={gestorSeccion}
          gestorName={gestorName}
          gestorEmail={user?.email || ''}
          userRole={userData?.rol || 'gestor'}
          onClose={() => setSelectedClient(null)}
          onUpdate={() => { setSelectedClient(null); loadClients(); }}
        />
      )}
    </div>
  );
}

function StatCard({ icon, label, value, color, small }) {
  const colors = {
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-600', icon: 'text-indigo-500' },
    amber: { bg: 'bg-amber-50', text: 'text-amber-600', icon: 'text-amber-500' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', icon: 'text-emerald-500' },
    rose: { bg: 'bg-rose-50', text: 'text-rose-600', icon: 'text-rose-500' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', icon: 'text-orange-500' },
  };
  const c = colors[color] || colors.indigo;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-lg ${c.bg} flex items-center justify-center ${c.icon}`}>
          {icon}
        </div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className={`${small ? 'text-lg' : 'text-2xl'} font-bold text-gray-900`}>{value}</p>
    </div>
  );
}
