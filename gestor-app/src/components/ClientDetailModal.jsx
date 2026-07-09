import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { doc, updateDoc, serverTimestamp, collection, addDoc, setDoc, getDoc, getDocs, deleteDoc, writeBatch } from 'firebase/firestore';
import { db, auth } from '../services/firebase';
import { useGeolocation } from '../hooks/useGeolocation';
import { downloadSingleLetter } from '../services/letterGenerator';
import { getClientLetters, getLetterUrl } from '../services/documentService';
import { printImageFromUrl } from '../services/printService';
import { generateAndPublishLetterJpg } from '../services/letterJpgService';
import { createAlert } from '../services/alertService';
import { getCatalogoNiveles, buildCascadingOptions } from '../services/nivelCatalogService';
import { getEstructuraTerritorial } from '../services/catalogService';
import DocumentViewerModal from './DocumentViewerModal';
import Toast from './Toast';
import {
  X, MapPin, Phone, Mail, User, FileText, Clock, Navigation,
  CheckCircle, XCircle, AlertTriangle, Loader2, FileDown, Copy,
  Flame, ShieldAlert, CreditCard, ChevronDown, Calendar, DollarSign,
  Send, Map, ArrowRight, ImagePlus
} from 'lucide-react';

// Threshold for high-value debt indicator (S/)
const HIGH_VALUE_THRESHOLD = 500;

// Alert-triggering states
const ALERT_STATES = ['suplantacion', 'pago_no_registrado'];

export default function ClientDetailModal({ client, seccion, gestorName, gestorEmail, onClose, onUpdate, userRole }) {
  const [updating, setUpdating] = useState(false);
  const [note, setNote] = useState('');
  const [downloadingLetter, setDownloadingLetter] = useState(false);
  const [generatingJpg, setGeneratingJpg] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(() => {
    const nc = Number(client?.numero_carta || 0);
    if (nc >= 1 && nc <= 5) return nc;
    const tramo = Number(client?.tramo_actual || 1);
    if (tramo <= 1) return 1;
    if (tramo === 2) return 3;
    if (tramo >= 3) return 5;
    return 1;
  });
  const [clientLetters, setClientLetters] = useState([]);
  const [lettersLoading, setLettersLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerUrl, setViewerUrl] = useState('');
  const [activeLetter, setActiveLetter] = useState(null);
  const { location, error: geoError, loading: geoLoading, getLocation } = useGeolocation();
  const [gpsAttempted, setGpsAttempted] = useState(false);

  // Nivel catalog state
  const [catalogo, setCatalogo] = useState(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [canal, setCanal] = useState('CAM');
  const [nivel1, setNivel1] = useState('');
  const [nivel2, setNivel2] = useState('');
  const [nivel3, setNivel3] = useState('');
  const [nivel4, setNivel4] = useState('');
  const [fechaPromesa, setFechaPromesa] = useState('');
  const [montoPromesa, setMontoPromesa] = useState('');

  const showToast = useCallback((message, variant = 'info') => {
    setToast({ message, variant });
  }, []);

  const dismissToast = useCallback(() => setToast(null), []);
  const isHighValue = parseFloat(client.importe_deuda_asignada || 0) > HIGH_VALUE_THRESHOLD;
  const isAsistente = userRole === 'asistente';
  const isAdminOrSupervisor = userRole === 'admin' || userRole === 'supervisor';

  // Zone editing state (admin/supervisor only)
  const [showZoneEdit, setShowZoneEdit] = useState(false);
  const [availableSections, setAvailableSections] = useState([]);
  const [zoneFilter, setZoneFilter] = useState('');
  const [savingZone, setSavingZone] = useState(false);
  const [contactPhone, setContactPhone] = useState(client?.telefono_movil || '');
  const [contactAddress, setContactAddress] = useState(client?.direccion || '');
  const [contactNote, setContactNote] = useState('');
  const [savingContact, setSavingContact] = useState(false);
  const [contactHistory, setContactHistory] = useState([]);
  const [loadingContactHistory, setLoadingContactHistory] = useState(false);

  // Load nivel catalog on mount
  useEffect(() => {
    getCatalogoNiveles().then(data => {
      setCatalogo(data);
      setCatalogLoading(false);
    });
  }, []);

  // Cascading options derived from current selections
  const niveles = catalogo?.niveles || [];
  const cascading = buildCascadingOptions(niveles, canal, nivel1, nivel2, nivel3);

  // Reset downstream selects when parent changes
  const handleCanalChange = (v) => { setCanal(v); setNivel1(''); setNivel2(''); setNivel3(''); setNivel4(''); };
  const handleN1Change = (v) => { setNivel1(v); setNivel2(''); setNivel3(''); setNivel4(''); };
  const handleN2Change = (v) => { setNivel2(v); setNivel3(''); setNivel4(''); };
  const handleN3Change = (v) => { setNivel3(v); setNivel4(''); };

  // Auto-set nivel4 if there's only one option
  useEffect(() => {
    if (cascading.nivel4Opts.length === 1 && !nivel4) {
      setNivel4(cascading.nivel4Opts[0]);
    }
  }, [cascading.nivel4Opts, nivel4]);

  // Determine if promesa fields are relevant (nivel2 contains "Promesa")
  const showPromesaFields = nivel2.toLowerCase().includes('promesa');

  // Can submit = all 4 niveles selected
  const nivelComplete = !!(nivel1 && nivel2 && nivel3 && nivel4);

  // Auto-capture GPS on modal open
  useEffect(() => {
    if (!location && !gpsAttempted) {
      setGpsAttempted(true);
      getLocation().catch(() => {});
    }
  }, [location, gpsAttempted, getLocation]);

  // GPS is MANDATORY — buttons disabled until we have a valid location
  const gpsReady = !!location;

  // Keyboard shortcuts: S for suplantacion, P for pago_no_registrado
  const handleKeyDown = useCallback((e) => {
    if (updating || !gpsReady) return;
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

    const keyMap = {
      's': 'suplantacion',
      'p': 'pago_no_registrado',
    };
    const status = keyMap[e.key.toLowerCase()];
    if (status) {
      e.preventDefault();
      handleStatusUpdate(status, { isSpecialState: true });
    }
  }, [updating, gpsReady]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    let ignore = false;
    const loadLetters = async () => {
      setLettersLoading(true);
      try {
        const letters = await getClientLetters({
          campaignId: client.campaignId || 'cartera_activa',
          clientId: client.codigo_cliente || client.id,
        });
        if (!ignore) setClientLetters(letters);
      } catch {
        if (!ignore) setClientLetters([]);
      } finally {
        if (!ignore) setLettersLoading(false);
      }
    };
    loadLetters();
    return () => {
      ignore = true;
    };
  }, [client.campaignId, client.codigo_cliente, client.id]);

  useEffect(() => {
    setContactPhone(client?.telefono_movil || '');
    setContactAddress(client?.direccion || '');
    setContactNote('');
  }, [client?.id, client?.telefono_movil, client?.direccion]);

  useEffect(() => {
    let ignore = false;
    const loadContactHistory = async () => {
      setLoadingContactHistory(true);
      try {
        const campaignId = client.campaignId || 'cartera_activa';
        const sectionPath = client.seccion_key || client.seccion;
        const clientId = client.id || client.codigo_cliente;
        const histRef = collection(
          db,
          'campañas', campaignId,
          'gestores', sectionPath,
          'clientes', clientId,
          'historial_contacto',
        );
        const snap = await getDocs(histRef);
        const rows = snap.docs.map(d => ({ id: d.id, ...d.data() }));
        rows.sort((a, b) => {
          const fa = new Date(a.fecha || 0).getTime();
          const fb = new Date(b.fecha || 0).getTime();
          return fb - fa;
        });
        if (!ignore) setContactHistory(rows.slice(0, 20));
      } catch {
        if (!ignore) setContactHistory([]);
      } finally {
        if (!ignore) setLoadingContactHistory(false);
      }
    };
    loadContactHistory();
    return () => { ignore = true; };
  }, [client?.campaignId, client?.seccion_key, client?.seccion, client?.id, client?.codigo_cliente]);

  const handleStatusUpdate = async (status, { isSpecialState = false } = {}) => {
    // Double-check GPS is available (mandatory)
    if (!location) {
      showToast('Debes activar el GPS antes de registrar una visita.', 'error');
      return;
    }

    setUpdating(true);
    try {
      // Use composite seccion_key if available, fall back to seccion letter
      const sectionPath = client.seccion_key || client.seccion;
      const clientRef = doc(
        db,
        'campañas', client.campaignId,
        'gestores', sectionPath,
        'clientes', client.id
      );

      const updateData = {
        estado_gestion: status,
        fecha_gestion: serverTimestamp(),
        nota_gestor: note || '',
        gps_gestor: {
          latitude: location.latitude,
          longitude: location.longitude,
          accuracy: location.accuracy,
          timestamp: location.timestamp,
        },
      };

      // Add nivel fields for normal flow (not special states)
      if (!isSpecialState && nivel1) {
        updateData.nivel_1 = nivel1;
        updateData.nivel_2 = nivel2 || '';
        updateData.nivel_3 = nivel3 || '';
        updateData.nivel_4 = nivel4 || '';
        updateData.canal_gestion = canal || '';
      }

      // Add promesa fields if present
      if (fechaPromesa) updateData.fecha_promesa_pago = fechaPromesa;
      if (montoPromesa && parseFloat(montoPromesa) > 0) {
        updateData.monto_promesa_pago = parseFloat(montoPromesa);
      }

      await updateDoc(clientRef, updateData);

      // Save GPS as verified client location (for future gestors)
      if (location.latitude && location.longitude) {
        const uid = auth.currentUser?.uid;
        updateDoc(clientRef, {
          ubicacion_verificada: {
            lat: location.latitude,
            lng: location.longitude,
            accuracy: location.accuracy || 0,
            timestamp: new Date().toISOString(),
            gestor_uid: uid || '',
            gestor_nombre: gestorName || '',
          },
        }).catch(() => {});
      }

      // Record GPS tracking point for location history
      const uid = auth.currentUser?.uid;
      if (uid && location.latitude && location.longitude) {
        const trackRef = doc(db, 'ubicaciones_gestores', uid);
        addDoc(collection(trackRef, 'puntos'), {
          lat: location.latitude,
          lng: location.longitude,
          accuracy: location.accuracy || 0,
          timestamp: serverTimestamp(),
          fecha: new Date().toISOString(),
          cliente_id: client.id || '',
          cliente_nombre: client.nombre || client.titular || '',
          estado: status,
          seccion: seccion || client.seccion || '',
        }).catch(() => {});
        setDoc(trackRef, {
          ultima_lat: location.latitude,
          ultima_lng: location.longitude,
          ultima_accuracy: location.accuracy || 0,
          ultimo_timestamp: serverTimestamp(),
          ultimo_cliente: client.nombre || client.titular || '',
          ultimo_estado: status,
          seccion: seccion || client.seccion || '',
        }, { merge: true }).catch(() => {});
      }

      // Create real-time alert for critical states
      if (ALERT_STATES.includes(status)) {
        await createAlert({
          tipo: status,
          client,
          seccion: seccion || client.seccion,
          gestorEmail: gestorEmail || '',
          gestorName: gestorName || '',
          gps: location,
          nota: note || '',
          campaignId: client.campaignId || 'cartera_activa',
        });
      }

      onUpdate();
    } catch (err) {
      console.error('Error updating client:', err);
      showToast('Error al actualizar. Intenta de nuevo.', 'error');
    } finally {
      setUpdating(false);
    }
  };

  const handleDownloadLetter = async () => {
    setDownloadingLetter(true);
    try {
      await downloadSingleLetter(client, seccion || client.seccion, gestorName || '');
    } catch (err) {
      showToast(`Error al generar carta: ${err.message}`, 'error');
    } finally {
      setDownloadingLetter(false);
    }
  };

  const handleOpenLetter = async (letter) => {
    try {
      const url = await getLetterUrl(letter);
      setActiveLetter(letter);
      setViewerUrl(url);
      setViewerOpen(true);
    } catch (err) {
      showToast(`No se pudo abrir la carta: ${err.message}`, 'error');
    }
  };

  const handleGenerateLetterJpg = async () => {
    setGeneratingJpg(true);
    try {
      const campaignId = client.campaignId || 'cartera_activa';
      const campaignSnap = await getDoc(doc(db, 'campañas', campaignId));
      const campaignName = campaignSnap.exists() ? (campaignSnap.data()?.nombre || '') : '';
      const result = await generateAndPublishLetterJpg({
        client,
        campaignId,
        gestorName: gestorName || '',
        campaignName,
        templateId: selectedTemplate,
      });
      const letters = await getClientLetters({
        campaignId: client.campaignId || 'cartera_activa',
        clientId: client.codigo_cliente || client.id,
      });
      setClientLetters(letters);
      if (result.mode === 'server') {
        showToast('Se encontró una carta ya publicada en servidor y se reutilizó.', 'info');
      } else {
        showToast('Carta JPG generada y publicada correctamente.', 'success');
      }
    } catch (err) {
      showToast(`No se pudo generar la carta JPG: ${err.message}`, 'error');
    } finally {
      setGeneratingJpg(false);
    }
  };

  const handleContactUpdate = async () => {
    const newPhone = (contactPhone || '').trim();
    const newAddress = (contactAddress || '').trim();
    const noteText = (contactNote || '').trim();
    if (!noteText) {
      showToast('Debe registrar una nota explicando el cambio de contacto.', 'error');
      return;
    }
    const currentPhone = client.telefono_movil || '';
    const currentAddress = client.direccion || '';
    if (newPhone === currentPhone && newAddress === currentAddress) {
      showToast('No hay cambios en dirección o teléfono para guardar.', 'error');
      return;
    }
    setSavingContact(true);
    try {
      const campaignId = client.campaignId || 'cartera_activa';
      const sectionPath = client.seccion_key || client.seccion;
      const clientId = client.id || client.codigo_cliente;
      const clientRef = doc(
        db,
        'campañas', campaignId,
        'gestores', sectionPath,
        'clientes', clientId,
      );
      const uid = auth.currentUser?.uid || '';
      const nowIso = new Date().toISOString();
      const changeEntry = {
        fecha: nowIso,
        campo: 'contacto',
        direccion_anterior: currentAddress || '',
        direccion_nueva: newAddress || '',
        telefono_anterior: currentPhone || '',
        telefono_nuevo: newPhone || '',
        nota: noteText,
        usuario_uid: uid,
        usuario_nombre: gestorName || '',
        usuario_email: gestorEmail || '',
        rol_editor: userRole || '',
        seccion_key: sectionPath || '',
        origen_actualizacion: 'web',
        gps: location ? {
          latitude: location.latitude,
          longitude: location.longitude,
          accuracy: location.accuracy,
          timestamp: location.timestamp,
        } : null,
      };

      await updateDoc(clientRef, {
        telefono_movil: newPhone,
        direccion: newAddress,
        ultima_nota_contacto: noteText,
        fecha_actualizacion_contacto: serverTimestamp(),
        fecha_actualizacion_contacto_iso: nowIso,
        actualizado_por_uid: uid,
        actualizado_por_nombre: gestorName || '',
        actualizado_por_email: gestorEmail || '',
        origen_actualizacion: 'web',
      });
      await addDoc(collection(clientRef, 'historial_contacto'), changeEntry);

      setContactHistory(prev => [changeEntry, ...prev].slice(0, 20));
      setContactNote('');
      onUpdate();
      showToast('Contacto actualizado y registrado en historial.', 'success');
    } catch (err) {
      console.error('Error updating contact data:', err);
      showToast('Error al actualizar contacto. Intenta de nuevo.', 'error');
    } finally {
      setSavingContact(false);
    }
  };

  const handleDownloadJpg = async () => {
    if (!activeLetter) return;
    const url = await getLetterUrl(activeLetter);
    const a = document.createElement('a');
    a.href = url;
    a.download = activeLetter.nombre_archivo || 'carta.jpg';
    a.click();
  };

  const handlePrintJpg = async () => {
    if (!activeLetter) return;
    const url = await getLetterUrl(activeLetter);
    await printImageFromUrl(url, activeLetter.nombre_archivo || 'Carta de Cobranza');
  };

  // ── Zone editing (admin/supervisor only) ──────────────────
  const handleOpenZoneEdit = async () => {
    setShowZoneEdit(true);
    try {
      const regiones = await getEstructuraTerritorial();
      const keys = [];
      for (const [r, rdata] of Object.entries(regiones)) {
        for (const [z, zdata] of Object.entries(rdata?.zonas || {})) {
          for (const s of (zdata?.secciones || [])) {
            keys.push(`${r}_${z}_${s}`);
          }
        }
      }
      keys.sort();
      setAvailableSections(keys);
    } catch {
      setAvailableSections([]);
    }
  };

  const handleZoneChange = async (newKey) => {
    const currentKey = client.seccion_key || client.seccion;
    if (newKey === currentKey) return;

    if (!window.confirm(
      `¿Mover a "${client.nombre_completo || client.nombre || ''}" de sección ${currentKey} → ${newKey}?`
    )) return;

    setSavingZone(true);
    try {
      const campaignId = client.campaignId || 'cartera_activa';
      const clientId = client.id || client.codigo_cliente;

      // Read existing client data
      const oldRef = doc(db, 'campañas', campaignId, 'gestores', currentKey, 'clientes', clientId);
      const oldSnap = await getDoc(oldRef);
      if (!oldSnap.exists()) throw new Error('Cliente no encontrado en sección actual.');

      const clientData = oldSnap.data();
      const parts = newKey.split('_');
      const newLetter = parts[2] || newKey;

      // Build zone change history entry
      const historial = Array.isArray(clientData.historial_zona) ? clientData.historial_zona : [];
      historial.push({
        seccion_anterior: currentKey,
        seccion_nueva: newKey,
        fecha: new Date().toISOString(),
        admin_email: gestorEmail || '',
        admin_name: gestorName || '',
        motivo: 'edicion_manual',
      });

      // Update client data
      const newData = {
        ...clientData,
        seccion: newLetter,
        seccion_key: newKey,
        region: parts[0] || '',
        zona: parts[1] || '',
        historial_zona: historial,
      };

      // Ensure destination section doc exists
      const newGestorRef = doc(db, 'campañas', campaignId, 'gestores', newKey);
      const newGestorSnap = await getDoc(newGestorRef);
      if (!newGestorSnap.exists()) {
        await setDoc(newGestorRef, {
          seccion_key: newKey,
          seccion: newLetter,
          region: parts[0] || '',
          zona: parts[1] || '',
          num_clientes: 0,
          deuda_asignada_total: 0,
          deuda_pendiente_total: 0,
          fecha_asignacion: serverTimestamp(),
          estado: 'pendiente',
        });
      }

      // Batch: write to new location, delete from old
      const batch = writeBatch(db);
      const newClientRef = doc(db, 'campañas', campaignId, 'gestores', newKey, 'clientes', clientId);
      batch.set(newClientRef, newData);
      batch.delete(oldRef);
      await batch.commit();

      showToast('Zona actualizada correctamente.', 'success');
      setShowZoneEdit(false);
      onUpdate();
    } catch (err) {
      console.error('Error changing zone:', err);
      showToast(`Error al cambiar zona: ${err.message}`, 'error');
    } finally {
      setSavingZone(false);
    }
  };

  const nombre = client.nombre_completo || '—';
  const direccionFull = [client.direccion, client.distrito, client.departamento].filter(Boolean).join(', ');
  const deudaAsignada = parseFloat(client.importe_deuda_asignada || 0);
  const deudaPendiente = parseFloat(client.importe_deuda_pendiente || 0);
  const mapsLat = Number(
    client?.ubicacion_verificada?.lat
    || client?.coordenada_y
    || 0
  );
  const mapsLng = Number(
    client?.ubicacion_verificada?.lng
    || client?.coordenada_x
    || 0
  );
  const hasMapsCoords = !!(mapsLat && mapsLng);

  return createPortal(
    <>
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full sm:max-w-lg md:max-w-xl lg:max-w-2xl bg-white rounded-t-3xl sm:rounded-3xl
                      max-h-[92vh] sm:max-h-[90vh] overflow-y-auto shadow-2xl animate-slide-up">
        {/* Header */}
        <div className="sticky top-0 bg-white/95 backdrop-blur-xl border-b border-slate-100 px-6 py-4
                        flex items-center justify-between rounded-t-3xl z-10">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-sm
              ${isHighValue
                ? 'bg-gradient-to-br from-orange-500 to-red-500'
                : 'bg-gradient-to-br from-indigo-500 to-violet-500'}`}>
              {isHighValue
                ? <Flame size={18} className="text-white" />
                : <span className="text-white text-sm font-bold">{nombre.charAt(0).toUpperCase()}</span>
              }
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
                Detalle del Cliente
                {isHighValue && (
                  <span className="text-[10px] bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-bold
                               uppercase tracking-wider border border-orange-200 animate-pulse">
                    Alto Valor
                  </span>
                )}
              </h2>
              <p className="text-[11px] text-slate-400 font-medium">Código: {client.codigo_cliente || '—'}</p>
            </div>
          </div>
          <button onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-xl transition-all text-slate-400 hover:text-slate-600">
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Client Info Card */}
          <div className="bg-slate-50 rounded-2xl p-4 space-y-3 border border-slate-100">
            <InfoRow icon={<User size={15} />} label="Nombre" value={nombre} bold />
            <InfoRow icon={<FileText size={15} />} label="DNI" value={client.numero_documento || '—'} />
            <InfoRow icon={<Phone size={15} />} label="Teléfono" value={client.telefono_movil || '—'} isPhone />
            <InfoRow icon={<Mail size={15} />} label="Correo" value={client.correo || '—'} />
            <InfoRow icon={<MapPin size={15} />} label="Dirección" value={direccionFull || '—'} />
            {client.referencia && (
              <InfoRow icon={<Navigation size={15} />} label="Referencia" value={client.referencia} />
            )}
            <InfoRow icon={<Clock size={15} />} label="Días de Atraso"
              value={<span className="text-amber-600 font-bold">{client.dias_atraso || 0} días</span>} />
            {/* Tramo info if available */}
            {client.tramo_actual && (
              <InfoRow icon={<FileText size={15} />} label="Tramo"
                value={<span className="text-indigo-600 font-bold">Tramo {client.tramo_actual}</span>} />
            )}
            {/* Section info */}
            <InfoRow icon={<Map size={15} />} label="Sección"
              value={
                <span className="text-slate-700 font-medium">
                  {client.seccion_key || client.seccion || '—'}
                </span>
              } />
            {/* Verified GPS location if available */}
            {client.ubicacion_verificada?.lat && (
              <InfoRow icon={<MapPin size={15} />} label="GPS Verificado"
                value={
                  <span className="text-emerald-600 text-xs font-medium">
                    {client.ubicacion_verificada.lat.toFixed(5)}, {client.ubicacion_verificada.lng.toFixed(5)}
                    <span className="text-slate-400 ml-1">
                      ({client.ubicacion_verificada.gestor_nombre || 'gestor'})
                    </span>
                  </span>
                } />
            )}
            {hasMapsCoords && (
              <a
                href={`https://www.google.com/maps?q=${mapsLat},${mapsLng}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 mt-2 text-xs px-3 py-2 rounded-lg
                           bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold"
              >
                <Map size={14} />
                Abrir en Google Maps
              </a>
            )}
          </div>

          {/* Contact update + history */}
          <div className="bg-sky-50/50 border border-sky-200 rounded-2xl p-4 space-y-3">
            <p className="text-xs font-bold uppercase tracking-wider text-sky-700">
              Actualizar contacto y ubicación
            </p>
            <div className="grid grid-cols-1 gap-2">
              <label className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider">
                Teléfono móvil
              </label>
              <input
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="Nuevo teléfono"
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white
                         text-sm focus:border-sky-400 focus:ring-2 focus:ring-sky-50 outline-none"
              />
              <label className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider mt-1">
                Dirección
              </label>
              <input
                value={contactAddress}
                onChange={(e) => setContactAddress(e.target.value)}
                placeholder="Nueva dirección"
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white
                         text-sm focus:border-sky-400 focus:ring-2 focus:ring-sky-50 outline-none"
              />
              <label className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider mt-1">
                Nota del cambio (obligatoria)
              </label>
              <textarea
                value={contactNote}
                onChange={(e) => setContactNote(e.target.value)}
                rows={2}
                placeholder="Ej: Cliente mudó domicilio, vecino confirmó nuevo número."
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white
                         text-sm focus:border-sky-400 focus:ring-2 focus:ring-sky-50 outline-none resize-none"
              />
            </div>
            <button
              onClick={handleContactUpdate}
              disabled={savingContact}
              className="w-full py-3 bg-sky-600 hover:bg-sky-700 text-white rounded-xl
                       font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {savingContact ? <Loader2 size={15} className="animate-spin" /> : <MapPin size={15} />}
              {savingContact ? 'Guardando cambio...' : 'Guardar cambio de contacto'}
            </button>

            <div className="bg-white border border-sky-100 rounded-xl p-3">
              <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider mb-2">
                Historial de contacto
              </p>
              {loadingContactHistory ? (
                <p className="text-xs text-slate-400">Cargando historial...</p>
              ) : contactHistory.length === 0 ? (
                <p className="text-xs text-slate-400">Sin cambios de contacto registrados.</p>
              ) : (
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {contactHistory.map((h, idx) => (
                    <div key={h.id || idx} className="text-xs border border-slate-100 rounded-lg p-2">
                      <p className="font-semibold text-slate-700">
                        {h.fecha ? String(h.fecha).slice(0, 16).replace('T', ' ') : 'Sin fecha'} · {h.usuario_nombre || 'Usuario'}
                      </p>
                      <p className="text-slate-600">Tel: {h.telefono_anterior || '—'} → {h.telefono_nuevo || '—'}</p>
                      <p className="text-slate-600">Dir: {h.direccion_anterior || '—'} → {h.direccion_nueva || '—'}</p>
                      <p className="text-slate-500 italic">{h.nota || ''}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Zone Edit (admin/supervisor only) */}
          {isAdminOrSupervisor && !showZoneEdit && (
            <button
              onClick={handleOpenZoneEdit}
              className="w-full py-2.5 bg-slate-50 hover:bg-slate-100 text-slate-600 font-semibold
                       rounded-2xl transition-all flex items-center justify-center gap-2 text-sm
                       border border-slate-200 active:scale-[0.98]"
            >
              <Map size={15} />
              Cambiar Zona / Sección
            </button>
          )}

          {isAdminOrSupervisor && showZoneEdit && (
            <div className="bg-indigo-50/50 border border-indigo-200 rounded-2xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-indigo-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Map size={14} /> Cambiar Zona
                </p>
                <button onClick={() => setShowZoneEdit(false)}
                  className="p-1 hover:bg-indigo-100 rounded-lg transition-colors">
                  <X size={16} className="text-indigo-400" />
                </button>
              </div>
              <p className="text-[11px] text-indigo-600">
                Actual: <span className="font-bold">{client.seccion_key || client.seccion || '—'}</span>
              </p>
              <input
                type="text"
                value={zoneFilter}
                onChange={e => setZoneFilter(e.target.value)}
                placeholder="Buscar sección..."
                className="w-full px-3 py-2 rounded-xl border border-indigo-200 bg-white
                         text-sm focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50 outline-none"
              />
              <div className="max-h-40 overflow-y-auto space-y-1">
                {availableSections.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-2">Cargando secciones…</p>
                ) : (
                  availableSections
                    .filter(k => k !== (client.seccion_key || client.seccion))
                    .filter(k => !zoneFilter || k.toLowerCase().includes(zoneFilter.toLowerCase()))
                    .map(k => (
                      <button key={k}
                        onClick={() => handleZoneChange(k)}
                        disabled={savingZone}
                        className="w-full text-left px-3 py-2 rounded-xl text-sm font-medium
                                 hover:bg-indigo-100 text-slate-700 transition-colors
                                 flex items-center justify-between disabled:opacity-50"
                      >
                        <span>{k}</span>
                        <ArrowRight size={14} className="text-indigo-400" />
                      </button>
                    ))
                )}
              </div>
              {savingZone && (
                <div className="flex items-center gap-2 text-xs text-indigo-500 justify-center py-1">
                  <Loader2 size={14} className="animate-spin" /> Moviendo cliente…
                </div>
              )}
            </div>
          )}

          {/* Debt Card — hidden for asistente role */}
          {!isAsistente && (
            <div className={`rounded-2xl p-5 text-white shadow-lg
              ${isHighValue
                ? 'bg-gradient-to-br from-orange-500 to-red-600 shadow-orange-500/20'
                : 'bg-gradient-to-br from-indigo-500 to-violet-600 shadow-indigo-500/20'}`}>
              <div className="flex items-center justify-between mb-3">
                <p className={`text-xs font-semibold uppercase tracking-wider
                  ${isHighValue ? 'text-orange-200' : 'text-indigo-200'}`}>
                  Información de Deuda
                </p>
                {isHighValue && (
                  <span className="flex items-center gap-1 text-xs bg-white/20 px-2.5 py-1 rounded-full font-bold">
                    <Flame size={12} /> {'>'} S/ {HIGH_VALUE_THRESHOLD}
                  </span>
                )}
              </div>
              <div className="flex justify-between items-center mb-3">
                <span className={`text-sm ${isHighValue ? 'text-orange-100' : 'text-indigo-100'}`}>
                  Deuda Asignada
                </span>
                <span className="text-xl font-extrabold">
                  S/ {deudaAsignada.toFixed(2)}
                </span>
              </div>
              <div className="h-px bg-white/20 my-2" />
              <div className="flex justify-between items-center">
                <span className={`text-sm ${isHighValue ? 'text-orange-100' : 'text-indigo-100'}`}>
                  Deuda Pendiente
                </span>
                <span className="text-xl font-extrabold">
                  S/ {deudaPendiente.toFixed(2)}
                </span>
              </div>
            </div>
          )}

          {/* Download letter button */}
          <button
            onClick={handleDownloadLetter}
            disabled={downloadingLetter}
            className="w-full py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold
                     rounded-2xl transition-all flex items-center justify-center gap-2.5 text-sm
                     border border-slate-200 active:scale-[0.98] disabled:opacity-50"
          >
            {downloadingLetter ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <FileDown size={16} />
            )}
            {downloadingLetter ? 'Generando...' : 'Descargar Carta de Cobranza'}
          </button>

          <div className="bg-indigo-50/50 border border-indigo-200 rounded-2xl p-4 space-y-3">
            <p className="text-xs font-bold uppercase tracking-wider text-indigo-700">
              Generar carta JPG para imprimir
            </p>
            <div className="flex items-center gap-2">
              <select
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(Number(e.target.value))}
                className="flex-1 px-3 py-2 rounded-xl border border-indigo-200 bg-white text-sm
                         focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50 outline-none"
              >
                <option value={1}>Carta 1 (E1-1)</option>
                <option value={2}>Carta 2 (E1-2)</option>
                <option value={3}>Carta 3 (E2-1)</option>
                <option value={4}>Carta 4 (E2-2)</option>
                <option value={5}>Carta 5 (E3-1)</option>
              </select>
              <button
                onClick={handleGenerateLetterJpg}
                disabled={generatingJpg}
                className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold
                         disabled:opacity-60 flex items-center gap-2"
              >
                {generatingJpg ? <Loader2 size={15} className="animate-spin" /> : <ImagePlus size={15} />}
                {generatingJpg ? 'Generando...' : 'Generar JPG'}
              </button>
            </div>
            <p className="text-[11px] text-indigo-500">
              Flujo hibrido: primero intenta usar carta ya publicada en servidor; si no existe, genera local y publica.
            </p>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
              Cartas JPG publicadas
            </p>
            {lettersLoading ? (
              <p className="text-sm text-slate-400">Cargando cartas...</p>
            ) : clientLetters.length === 0 ? (
              <p className="text-sm text-slate-500">No hay cartas JPG publicadas para este cliente.</p>
            ) : (
              <div className="space-y-2">
                {clientLetters.map((letter) => (
                  <button
                    key={letter.id}
                    onClick={() => handleOpenLetter(letter)}
                    className="w-full text-left px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50"
                  >
                    <p className="text-sm font-semibold text-slate-700">{letter.nombre_archivo || 'Carta'}</p>
                    <p className="text-xs text-slate-400">Carta #{letter.numero_carta || '-'} · JPG</p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* GPS Section — MANDATORY */}
          <div className={`rounded-2xl p-4 border
            ${gpsReady
              ? 'bg-emerald-50/50 border-emerald-200'
              : 'bg-amber-50/50 border-amber-200'}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-bold text-slate-700 flex items-center gap-2">
                <MapPin size={15} className={gpsReady ? 'text-emerald-500' : 'text-amber-500'} />
                Ubicación GPS
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider
                  ${gpsReady
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-amber-100 text-amber-700'}`}>
                  {gpsReady ? '✓ Capturado' : 'Requerido'}
                </span>
              </span>
              <button
                onClick={() => getLocation().catch(() => {})}
                disabled={geoLoading}
                className="text-xs bg-indigo-500 text-white px-4 py-2 rounded-xl font-semibold
                         hover:bg-indigo-600 active:bg-indigo-700 transition-all
                         disabled:opacity-50 flex items-center gap-1.5
                         shadow-sm shadow-indigo-500/20"
              >
                {geoLoading ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Navigation size={12} />
                )}
                {geoLoading ? 'Obteniendo...' : gpsReady ? 'Recapturar' : 'Capturar'}
              </button>
            </div>
            {location && (
              <div className="text-xs text-emerald-700 bg-emerald-50 rounded-xl px-4 py-3 mt-2
                           border border-emerald-200/50 font-medium">
                <p>✓ Lat: {location.latitude.toFixed(6)}, Lng: {location.longitude.toFixed(6)}</p>
                <p className="text-emerald-500 mt-0.5">Precisión: ±{location.accuracy.toFixed(0)}m</p>
              </div>
            )}
            {geoError && (
              <div className="mt-2 space-y-1">
                <p className="text-xs text-red-500 font-medium">{geoError}</p>
                <p className="text-[11px] text-red-400">
                  ⚠️ El GPS es obligatorio. Activa la ubicación en tu dispositivo e intenta de nuevo.
                </p>
              </div>
            )}
            {!gpsReady && !geoLoading && !geoError && (
              <p className="text-[11px] text-amber-600 mt-2 font-medium">
                📍 Esperando captura de GPS... Esto es obligatorio para registrar la visita.
              </p>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">
              Nota de gestión
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ej: Casa cerrada, perro en la entrada, vecino dice que viajó..."
              rows={3}
              className="w-full px-4 py-3.5 rounded-2xl border border-slate-200 bg-slate-50/50
                       focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 focus:bg-white
                       outline-none transition-all text-sm text-slate-700
                       placeholder:text-slate-400 resize-none"
            />
          </div>

          {/* ── Nivel Selector (cascading dropdowns) ── */}
          <div className="space-y-3">
            <p className="text-sm font-bold text-slate-700">Resultado de la gestión:</p>

            {catalogLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-400 py-4 justify-center">
                <Loader2 size={16} className="animate-spin" /> Cargando catálogo…
              </div>
            ) : !catalogo ? (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3 text-xs text-amber-700">
                No se encontró el catálogo de niveles. Solicite al administrador que lo suba.
              </div>
            ) : (
              <>
                {/* Canal selector */}
                <div className="flex gap-2">
                  {(catalogo.canales || ['CAM', 'TEL']).map(c => (
                    <button key={c}
                      onClick={() => handleCanalChange(c)}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-bold transition-all
                        ${canal === c
                          ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20'
                          : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                      {c === 'CAM' ? '🚶 Campo (CAM)' : '📞 Teléfono (TEL)'}
                    </button>
                  ))}
                </div>

                {/* Nivel 1 */}
                <NivelSelect
                  label="Nivel 1"
                  value={nivel1}
                  options={cascading.nivel1Opts}
                  onChange={handleN1Change}
                  placeholder="Seleccione tipo de contacto…"
                />

                {/* Nivel 2 */}
                {nivel1 && (
                  <NivelSelect
                    label="Nivel 2"
                    value={nivel2}
                    options={cascading.nivel2Opts}
                    onChange={handleN2Change}
                    placeholder="Seleccione resultado…"
                  />
                )}

                {/* Nivel 3 */}
                {nivel2 && (
                  <NivelSelect
                    label="Nivel 3"
                    value={nivel3}
                    options={cascading.nivel3Opts}
                    onChange={handleN3Change}
                    placeholder="Seleccione detalle…"
                  />
                )}

                {/* Nivel 4 */}
                {nivel3 && (
                  <NivelSelect
                    label="Nivel 4"
                    value={nivel4}
                    options={cascading.nivel4Opts}
                    onChange={setNivel4}
                    placeholder="Seleccione sub-detalle…"
                  />
                )}

                {/* Promesa fields */}
                {showPromesaFields && (
                  <div className="bg-indigo-50/50 border border-indigo-200 rounded-2xl p-4 space-y-3">
                    <p className="text-xs font-bold text-indigo-700 uppercase tracking-wider">
                      Datos de Promesa de Pago
                    </p>
                    <div className="flex gap-3">
                      <div className="flex-1">
                        <label className="text-[11px] text-slate-500 font-medium flex items-center gap-1 mb-1">
                          <Calendar size={12} /> Fecha promesa
                        </label>
                        <input type="date" value={fechaPromesa}
                          onChange={e => setFechaPromesa(e.target.value)}
                          className="w-full px-3 py-2.5 rounded-xl border border-slate-200 bg-white
                                   text-sm focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50 outline-none" />
                      </div>
                      <div className="flex-1">
                        <label className="text-[11px] text-slate-500 font-medium flex items-center gap-1 mb-1">
                          <DollarSign size={12} /> Monto (S/)
                        </label>
                        <input type="number" step="0.01" min="0" value={montoPromesa}
                          onChange={e => setMontoPromesa(e.target.value)}
                          placeholder="0.00"
                          className="w-full px-3 py-2.5 rounded-xl border border-slate-200 bg-white
                                   text-sm focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50 outline-none" />
                      </div>
                    </div>
                  </div>
                )}

                {/* Submit button */}
                <button
                  onClick={() => handleStatusUpdate(mapNivelToEstado(nivel1))}
                  disabled={updating || !gpsReady || !nivelComplete}
                  className={`w-full py-4 bg-gradient-to-r from-indigo-500 to-violet-500
                             hover:from-indigo-600 hover:to-violet-600
                             text-white font-bold rounded-2xl transition-all text-[15px]
                             disabled:opacity-40 disabled:cursor-not-allowed
                             flex items-center justify-center gap-3
                             shadow-lg shadow-indigo-500/20 active:scale-[0.98]`}
                >
                  {updating ? <Loader2 size={22} className="animate-spin" /> : <Send size={20} />}
                  Registrar Gestión
                </button>
              </>
            )}

            {!gpsReady && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3 flex items-center gap-2">
                <MapPin size={16} className="text-amber-500 shrink-0" />
                <p className="text-xs text-amber-700 font-medium">
                  Captura tu ubicación GPS para habilitar el registro.
                </p>
              </div>
            )}
          </div>

          {/* ── Special states (alerts) ── */}
          <div className="space-y-3 pb-6">
            <div className="flex items-center gap-3 pt-1">
              <div className="flex-1 h-px bg-slate-200" />
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                Estados especiales
              </span>
              <div className="flex-1 h-px bg-slate-200" />
            </div>

            <StatusButton
              code="S"
              label="SUPLANTACIÓN"
              subLabel="Genera alerta a central"
              icon={<ShieldAlert size={22} />}
              gradient="from-red-600 to-rose-600"
              hoverGradient="from-red-700 to-rose-700"
              shadow="shadow-red-500/20"
              disabled={updating || !gpsReady}
              loading={updating}
              onClick={() => handleStatusUpdate('suplantacion', { isSpecialState: true })}
            />

            <StatusButton
              code="P"
              label="PAGO NO REGISTRADO"
              subLabel="Genera alerta a central"
              icon={<CreditCard size={22} />}
              gradient="from-blue-600 to-cyan-600"
              hoverGradient="from-blue-700 to-cyan-700"
              shadow="shadow-blue-500/20"
              disabled={updating || !gpsReady}
              loading={updating}
              onClick={() => handleStatusUpdate('pago_no_registrado', { isSpecialState: true })}
            />
          </div>
        </div>
      </div>

      <DocumentViewerModal
        open={viewerOpen}
        title={activeLetter?.nombre_archivo || 'Carta de cobranza'}
        imageUrl={viewerUrl}
        onClose={() => setViewerOpen(false)}
        onDownload={handleDownloadJpg}
        onPrint={handlePrintJpg}
      />

      <style>{`
        @keyframes slide-up {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .animate-slide-up {
          animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
    </div>

      <Toast
        message={toast?.message}
        variant={toast?.variant}
        onClose={dismissToast}
      />
    </>,
    document.body,
  );
}

function StatusButton({ code, label, subLabel, icon, gradient, hoverGradient, shadow, disabled, loading, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full py-4 bg-gradient-to-r ${gradient}
                 hover:bg-gradient-to-r ${hoverGradient}
                 text-white font-bold rounded-2xl transition-all text-[15px]
                 disabled:opacity-40 disabled:cursor-not-allowed
                 flex items-center justify-center gap-3
                 shadow-lg ${shadow} active:scale-[0.98]`}
    >
      {loading ? <Loader2 size={22} className="animate-spin" /> : icon}
      <div className="flex flex-col items-start">
        <span>{label}</span>
        {subLabel && <span className="text-[10px] opacity-80 font-medium">{subLabel}</span>}
      </div>
      <span className="ml-auto text-xs opacity-60 bg-white/20 w-7 h-7 rounded-lg
                     flex items-center justify-center font-bold">
        {code}
      </span>
    </button>
  );
}

function NivelSelect({ label, value, options, onChange, placeholder }) {
  return (
    <div>
      <label className="block text-[11px] text-slate-500 font-semibold uppercase tracking-wider mb-1">
        {label}
      </label>
      <div className="relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white
                   text-sm text-slate-700 appearance-none cursor-pointer
                   focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50 outline-none
                   transition-all font-medium"
        >
          <option value="">{placeholder}</option>
          {options.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
        <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
      </div>
    </div>
  );
}

/**
 * Map a nivel1 value to a backward-compatible estado_gestion.
 */
function mapNivelToEstado(nivel1) {
  const map = {
    'Contacto efectivo': 'visitado_habido',
    'Contacto no efectivo': 'visitado_no_habido',
    'No contacto': 'visitado_no_habido',
  };
  return map[nivel1] || 'visitado_habido';
}

function InfoRow({ icon, label, value, bold, isPhone }) {
  return (
    <div className="flex items-start gap-3">
      <div className="text-slate-400 mt-0.5 shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">{label}</p>
        {isPhone && value !== '—' ? (
          <a href={`tel:${value}`} className="text-sm text-indigo-600 font-semibold hover:underline">
            {value}
          </a>
        ) : typeof value === 'string' ? (
          <p className={`text-sm ${bold ? 'font-bold text-slate-800' : 'text-slate-700'} break-words`}>
            {value}
          </p>
        ) : (
          <div className="text-sm">{value}</div>
        )}
      </div>
    </div>
  );
}
