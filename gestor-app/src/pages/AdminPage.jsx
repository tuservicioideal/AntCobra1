import { useState, useEffect, useMemo } from 'react';
import { collection, getDocs, doc, setDoc, deleteDoc, query, where } from 'firebase/firestore';
import { db } from '../services/firebase';
import { signOut } from 'firebase/auth';
import { auth } from '../services/firebase';
import { createUserWithPassword } from '../services/userCreation';
import { getActiveCampaignId } from '../services/campaignUtils';
import {
  UserPlus, Trash2, Edit3, ArrowLeft, Users, Shield,
  Save, X, AlertCircle, CheckCircle, LogOut, RefreshCw, Link2, MapPin, Eye, EyeOff
} from 'lucide-react';

export default function AdminPage({ onBack }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [message, setMessage] = useState(null);
  const [campaignSections, setCampaignSections] = useState([]);
  const [selectedKeys, setSelectedKeys] = useState([]);

  const [form, setForm] = useState({
    nombre: '', email: '', password: '', telefono: '', rol: 'gestor'
  });
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { loadUsers(); loadCampaignSections(); }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const snap = await getDocs(collection(db, 'usuarios'));
      const allDocs = snap.docs.map(d => ({ id: d.id, ...d.data() }));

      // De-duplicate by email: keep the doc with the most complete data
      const byEmail = {};
      for (const u of allDocs) {
        const email = (u.email || '').toLowerCase();
        if (!email) {
          byEmail[u.id] = u; // Keep docs without email by ID
          continue;
        }
        const existing = byEmail[email];
        if (!existing) {
          byEmail[email] = u;
        } else {
          // Keep the one with more complete data (has seccion, has uid, etc.)
          const existingScore = (existing.seccion ? 2 : 0) + (existing.uid ? 1 : 0) + (existing.nombre ? 1 : 0);
          const newScore = (u.seccion ? 2 : 0) + (u.uid ? 1 : 0) + (u.nombre ? 1 : 0);
          if (newScore > existingScore) {
            byEmail[email] = { ...existing, ...u }; // Merge, prefer new
          } else {
            byEmail[email] = { ...u, ...existing }; // Merge, prefer existing
          }
        }
      }
      setUsers(Object.values(byEmail));
    } catch (err) {
      console.error('Error loading users:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadCampaignSections = async () => {
    try {
      const campaignId = await getActiveCampaignId();
      if (!campaignId) return;
      const snap = await getDocs(collection(db, 'campañas', campaignId, 'gestores'));
      setCampaignSections(snap.docs.map(d => ({ id: d.id, ...d.data() })));
    } catch (err) {
      console.error('Error loading campaign sections:', err);
    }
  };

  // Build hierarchy: Region → Zone → Section[]
  const hierarchy = useMemo(() => {
    const tree = {};
    for (const s of campaignSections) {
      const r = s.region || '??';
      const z = s.zona || '??';
      if (!tree[r]) tree[r] = {};
      if (!tree[r][z]) tree[r][z] = [];
      tree[r][z].push(s);
    }
    return tree;
  }, [campaignSections]);

  const handleSave = async (e) => {
    e.preventDefault();
    const isAdminRole = form.rol === 'admin' || form.rol === 'supervisor';
    if (!form.nombre || !form.email) {
      setMessage({ type: 'error', text: 'Nombre y email son obligatorios' });
      return;
    }
    if (!editUser && !form.password) {
      setMessage({ type: 'error', text: 'La contraseña es obligatoria para nuevos usuarios' });
      return;
    }
    if (!editUser && form.password.length < 6) {
      setMessage({ type: 'error', text: 'La contraseña debe tener al menos 6 caracteres' });
      return;
    }
    if (!isAdminRole && selectedKeys.length === 0) {
      setMessage({ type: 'error', text: 'Selecciona al menos una sección para el gestor' });
      return;
    }
    setSaving(true);
    try {
      const normalizedEmail = form.email.trim().toLowerCase();
      const firstKey = selectedKeys[0] || '';
      const parts = firstKey.split('_');
      const profileData = {
        nombre: form.nombre.trim(),
        email: normalizedEmail,
        seccion: parts.length === 3 ? parts[2] : '',
        secciones: selectedKeys,
        region: parts.length === 3 ? parts[0] : '',
        zona: parts.length === 3 ? parts[1] : '',
        telefono: form.telefono.trim(),
        rol: form.rol,
        activo: true,
        fecha_actualizacion: new Date().toISOString(),
      };

      // Resolve the canonical doc ID:
      // 1. If editing, use the existing doc ID.
      // 2. For new users, create Firebase Auth account and use the UID.
      // 3. Otherwise, search by email to find existing UID-based doc.
      let userId = editUser?.id;
      if (!userId) {
        // Try to create Firebase Auth account for the new user
        if (form.password) {
          const result = await createUserWithPassword(
            normalizedEmail, form.password, form.nombre.trim()
          );
          if (result.error) {
            setMessage({ type: 'error', text: result.error });
            setSaving(false);
            return;
          }
          userId = result.uid;
        }
        // Fallback: search for existing doc by email
        if (!userId) {
          const q = query(collection(db, 'usuarios'), where('email', '==', normalizedEmail));
          const snap = await getDocs(q);
          if (!snap.empty) {
            const uidDoc = snap.docs.find((d) => d.id.length >= 20 && /[a-zA-Z0-9]/.test(d.id));
            userId = uidDoc ? uidDoc.id : snap.docs[0].id;
          } else {
            userId = normalizedEmail.replace(/[^a-zA-Z0-9]/g, '_');
          }
        }
      }
      await setDoc(doc(db, 'usuarios', userId), profileData, { merge: true });

      // Sync profile to any other duplicate docs for the same email
      const q = query(collection(db, 'usuarios'), where('email', '==', normalizedEmail));
      const snap = await getDocs(q);
      const syncPromises = [];
      snap.forEach((d) => {
        if (d.id !== userId) {
          syncPromises.push(
            setDoc(doc(db, 'usuarios', d.id), {
              seccion: profileData.seccion,
              secciones: profileData.secciones,
              region: profileData.region,
              zona: profileData.zona,
              nombre: profileData.nombre,
              telefono: profileData.telefono,
              rol: profileData.rol,
              fecha_actualizacion: profileData.fecha_actualizacion,
            }, { merge: true })
          );
        }
      });
      if (syncPromises.length > 0) {
        await Promise.allSettled(syncPromises);
        console.info(`[Admin] Synced profile to ${syncPromises.length} duplicate doc(s)`);
      }

      setMessage({ type: 'success', text: editUser ? 'Usuario actualizado (y sincronizado)' : 'Usuario creado con éxito. Ya puede iniciar sesión.' });
      setShowForm(false); setEditUser(null); resetForm(); loadUsers();
    } catch (err) {
      setMessage({ type: 'error', text: 'Error al guardar: ' + err.message });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`¿Eliminar a ${user.nombre}?`)) return;
    try {
      // Delete the main document
      await deleteDoc(doc(db, 'usuarios', user.id));

      // Also delete the email-derived duplicate doc and any other docs with same email
      const email = (user.email || '').toLowerCase();
      if (email) {
        const emailKey = email.replace(/[^a-zA-Z0-9]/g, '_');
        if (emailKey !== user.id) {
          try { await deleteDoc(doc(db, 'usuarios', emailKey)); } catch (e) { /* may not exist */ }
        }
        // Clean up any remaining docs with same email
        const q = query(collection(db, 'usuarios'), where('email', '==', email));
        const snap = await getDocs(q);
        const delPromises = [];
        snap.forEach((d) => {
          if (d.id !== user.id) delPromises.push(deleteDoc(doc(db, 'usuarios', d.id)));
        });
        await Promise.allSettled(delPromises);
      }

      setMessage({ type: 'success', text: 'Usuario eliminado' });
      loadUsers();
    } catch (err) {
      setMessage({ type: 'error', text: 'Error al eliminar: ' + err.message });
    }
  };

  const handleEdit = (user) => {
    setEditUser(user);
    setForm({
      nombre: user.nombre || '', email: user.email || '',
      password: '', telefono: user.telefono || '', rol: user.rol || 'gestor'
    });
    // Load composite keys or try to reconstruct from legacy fields
    let keys = [];
    if (user.secciones && Array.isArray(user.secciones)) {
      keys = user.secciones.filter(k => k.includes('_'));
    }
    if (keys.length === 0 && user.seccion && user.region && user.zona) {
      const ck = `${user.region}_${user.zona}_${user.seccion.toUpperCase()}`;
      if (campaignSections.some(s => s.id === ck)) keys = [ck];
    }
    setSelectedKeys(keys);
    setShowForm(true);
  };

  const resetForm = () => {
    setForm({ nombre: '', email: '', password: '', telefono: '', rol: 'gestor' });
    setSelectedKeys([]);
    setShowPassword(false);
  };

  return (
    <div className="app-page">
      {/* Header */}
      <header className="app-topbar">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {onBack && (
              <button onClick={onBack} className="app-back-btn">
                <ArrowLeft size={18} />
              </button>
            )}
            <div className="app-icon-chip">
              <Shield size={18} />
            </div>
            <div>
              <h1 className="app-topbar-title">Admin — Gestores</h1>
              <p className="app-topbar-subtitle">{users.length} usuarios registrados</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setEditUser(null); resetForm(); setShowForm(true); }}
              className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white
                       px-4 py-2.5 rounded-xl text-sm font-bold transition-all"
            >
              <UserPlus size={16} /> Nuevo
            </button>
            <button onClick={() => signOut(auth)}
              className="p-2.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all border border-slate-200">
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-5">
        {/* Messages */}
        {message && (
          <div className={`flex items-center gap-2.5 rounded-2xl px-4 py-3.5 mb-4 text-sm font-medium
            ${message.type === 'error'
              ? 'bg-red-50 border border-red-200/60 text-red-600'
              : 'bg-emerald-50 border border-emerald-200/60 text-emerald-600'
            }`}>
            {message.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
            {message.text}
            <button onClick={() => setMessage(null)} className="ml-auto hover:opacity-70">
              <X size={14} />
            </button>
          </div>
        )}

        {/* Form Modal */}
        {showForm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowForm(false)} />
            <div className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl p-7">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-extrabold text-slate-800">
                  {editUser ? 'Editar Gestor' : 'Nuevo Gestor'}
                </h2>
                <button onClick={() => setShowForm(false)}
                  className="p-2 hover:bg-slate-100 rounded-xl transition-all">
                  <X size={20} className="text-slate-400" />
                </button>
              </div>

              <form onSubmit={handleSave} className="space-y-4">
                <FormField label="Nombre completo" value={form.nombre}
                  onChange={(v) => setForm({ ...form, nombre: v })} placeholder="Juan Pérez" required />
                <FormField label="Correo electrónico" type="email" value={form.email}
                  onChange={(v) => setForm({ ...form, email: v })} placeholder="gestor@ejemplo.com"
                  required disabled={!!editUser} />

                {/* Password field — required for new users, optional for edit */}
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    {editUser ? 'Nueva contraseña (dejar vacío = sin cambio)' : 'Contraseña'}
                    {!editUser && <span className="text-red-400"> *</span>}
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      placeholder={editUser ? 'Sin cambios' : 'Mínimo 6 caracteres'}
                      required={!editUser}
                      minLength={!editUser ? 6 : undefined}
                      className="w-full px-4 py-3.5 pr-12 rounded-2xl border border-slate-200 bg-slate-50/50
                               focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 focus:bg-white
                               outline-none transition-all text-sm text-slate-700
                               placeholder:text-slate-400"
                    />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-slate-400
                               hover:text-slate-600 hover:bg-slate-100 transition-all">
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <FormField label="Teléfono" value={form.telefono}
                  onChange={(v) => setForm({ ...form, telefono: v })} placeholder="999888777" />

                {/* Section Selector — hidden for admin/supervisor */}
                {form.rol !== 'admin' && form.rol !== 'supervisor' && (
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                      Secciones asignadas <span className="text-red-400">*</span>
                    </label>
                    {campaignSections.length === 0 ? (
                      <p className="text-xs text-amber-600 bg-amber-50 rounded-xl p-3 border border-amber-200/60">
                        No se encontraron secciones en la campaña activa.
                        Sube un Excel desde la app de escritorio primero.
                      </p>
                    ) : (
                      <div className="max-h-52 overflow-y-auto border border-slate-200 rounded-2xl p-3 space-y-2
                                    bg-slate-50/50">
                        {Object.entries(hierarchy).sort(([a],[b]) => a.localeCompare(b)).map(([region, zones]) => (
                          <div key={region}>
                            <p className="text-xs font-bold text-indigo-600 flex items-center gap-1 mb-1">
                              <MapPin size={12} /> Región {region}
                            </p>
                            {Object.entries(zones).sort(([a],[b]) => a.localeCompare(b)).map(([zona, sections]) => (
                              <div key={zona} className="ml-4 mb-1">
                                <p className="text-[11px] text-slate-500 font-medium">Zona {zona}</p>
                                {sections.sort((a,b) => (a.seccion||'').localeCompare(b.seccion||'')).map((s) => (
                                  <label key={s.id}
                                    className={`flex items-center gap-2 ml-4 py-1 px-2 rounded-lg cursor-pointer
                                      transition-all text-sm ${selectedKeys.includes(s.id)
                                        ? 'bg-indigo-50 text-indigo-700 font-medium'
                                        : 'text-slate-600 hover:bg-slate-100'}`}>
                                    <input type="checkbox"
                                      checked={selectedKeys.includes(s.id)}
                                      onChange={(e) => {
                                        if (e.target.checked) setSelectedKeys(prev => [...prev, s.id]);
                                        else setSelectedKeys(prev => prev.filter(k => k !== s.id));
                                      }}
                                      className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                                    <span>Sección {s.seccion || s.id.split('_').pop()}</span>
                                    <span className="text-[10px] text-slate-400 ml-auto">
                                      {s.num_clientes || 0} clientes
                                    </span>
                                  </label>
                                ))}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                    {selectedKeys.length > 0 && (
                      <p className="text-xs text-indigo-500 mt-1.5 font-medium">
                        {selectedKeys.length} sección(es) seleccionada(s)
                      </p>
                    )}
                  </div>
                )}
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Rol</label>
                  <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })}
                    className="w-full px-4 py-3.5 rounded-2xl border border-slate-200 bg-slate-50/50
                             focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50
                             outline-none transition-all text-sm text-slate-700">
                    <option value="gestor">Gestor de Campo</option>
                    <option value="asistente">Asistente</option>
                    <option value="supervisor">Supervisor</option>
                    <option value="admin">Administrador</option>
                  </select>
                </div>
                <div className="flex gap-3 pt-3">
                  <button type="button" onClick={() => setShowForm(false)}
                    className="flex-1 py-3.5 border border-slate-200 text-slate-600 font-bold
                             rounded-2xl hover:bg-slate-50 transition-all text-sm">
                    Cancelar
                  </button>
                  <button type="submit" disabled={saving}
                    className="flex-1 py-3.5 bg-gradient-to-r from-indigo-600 to-violet-600
                             text-white font-bold rounded-2xl hover:from-indigo-700 hover:to-violet-700
                             transition-all flex items-center justify-center gap-2 text-sm
                             shadow-lg shadow-indigo-500/20 active:scale-[0.98]
                             disabled:opacity-60 disabled:cursor-not-allowed">
                    {saving ? (
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <>
                        <Save size={16} />
                        {editUser ? 'Actualizar' : 'Crear Usuario'}
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Users List */}
        {loading ? (
          <div className="flex flex-col items-center py-20">
            <div className="w-10 h-10 border-[3px] border-indigo-200 border-t-indigo-500 rounded-full animate-spin mb-4" />
            <p className="text-slate-500 text-sm font-medium">Cargando usuarios...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-20 h-20 bg-slate-100 rounded-3xl flex items-center justify-center mx-auto mb-4">
              <Users size={32} className="text-slate-300" />
            </div>
            <p className="text-slate-600 font-bold text-lg">No hay gestores registrados</p>
            <p className="text-slate-400 text-sm mt-2">Presiona "Nuevo" para agregar uno</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {users.map((user) => (
              <div key={user.id}
                className="bg-white rounded-2xl border border-slate-200/80 p-4
                         hover:border-indigo-200 hover:shadow-md hover:shadow-indigo-500/5 transition-all">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500
                                  flex items-center justify-center shadow-sm shadow-indigo-200/50">
                      <span className="text-white text-sm font-bold">{user.seccion || '?'}</span>
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-800 text-sm">{user.nombre}</h3>
                      <p className="text-xs text-slate-400 font-medium">{user.email}</p>
                      <div className="flex items-center gap-3 mt-1.5">
                        {user.telefono && (
                          <span className="text-[11px] text-slate-400">📱 {user.telefono}</span>
                        )}
                        {user.zona && (
                          <span className="text-[11px] text-slate-400">
                            📍 {user.secciones?.length > 1
                              ? `${user.secciones.length} secciones`
                              : user.region ? `R${user.region}/Z${user.zona}` : user.zona}
                          </span>
                        )}
                        <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-bold
                          ${user.rol === 'admin'
                            ? 'bg-purple-50 text-purple-600 ring-1 ring-purple-200'
                            : user.rol === 'supervisor'
                              ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200'
                              : user.rol === 'asistente'
                                ? 'bg-teal-50 text-teal-600 ring-1 ring-teal-200'
                                : 'bg-slate-50 text-slate-500 ring-1 ring-slate-200'
                          }`}>
                          {user.rol || 'gestor'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleEdit(user)}
                      className="p-2.5 text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 rounded-xl transition-all">
                      <Edit3 size={15} />
                    </button>
                    <button onClick={() => handleDelete(user)}
                      className="p-2.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Assignments summary — which section is assigned to whom */}
        {campaignSections.length > 0 && !loading && (
          <div className="mt-6 bg-white border border-slate-200/80 rounded-2xl p-5">
            <p className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
              <Link2 size={15} className="text-indigo-500" />
              Resumen de asignaciones
            </p>
            <div className="space-y-1.5">
              {campaignSections.sort((a,b) => a.id.localeCompare(b.id)).map((sec) => {
                const assignedUser = users.find(u =>
                  Array.isArray(u.secciones) && u.secciones.includes(sec.id)
                );
                return (
                  <div key={sec.id} className="flex items-center gap-2 text-sm py-1.5 px-3 rounded-lg bg-slate-50/70">
                    <span className="font-bold text-indigo-600 w-8 text-center">{sec.seccion || sec.id.split('_').pop()}</span>
                    <span className="text-[11px] text-slate-400 w-20">R{sec.region}·Z{sec.zona}</span>
                    <span className="text-[11px] text-slate-400 w-16">{sec.num_clientes || 0} clientes</span>
                    <span className="ml-auto text-xs truncate max-w-[150px]">
                      {assignedUser ? (
                        <span className="text-emerald-600 font-medium">→ {assignedUser.nombre}</span>
                      ) : (
                        <span className="text-amber-500 italic">sin asignar</span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Important note */}
        <div className="mt-6 bg-blue-50 border border-blue-200/60 rounded-2xl p-5">
          <p className="text-sm text-blue-700 font-bold mb-1.5">ℹ️ Cómo funciona la sincronización</p>
          <p className="text-xs text-blue-600 leading-relaxed">
            Al guardar un usuario, el sistema sincroniza automáticamente las secciones asignadas
            (con claves compuestas región_zona_sección) con <strong>todos los documentos de perfil</strong>
            vinculados a ese correo. Esto garantiza que el gestor vea sus secciones correctas al iniciar sesión.
          </p>
        </div>
        <div className="mt-3 bg-emerald-50 border border-emerald-200/60 rounded-2xl p-5">
          <p className="text-sm text-emerald-700 font-bold mb-1.5">✅ Creación de cuentas</p>
          <p className="text-xs text-emerald-600 leading-relaxed">
            Al crear un nuevo usuario desde esta página, se genera automáticamente
            su <strong>cuenta de autenticación</strong> con email y contraseña.
            El usuario podrá iniciar sesión inmediatamente con las credenciales asignadas.
          </p>
        </div>
      </main>
    </div>
  );
}

function FormField({ label, value, onChange, placeholder, type = 'text', required, maxLength, disabled }) {
  return (
    <div>
      <label className="block text-sm font-semibold text-slate-700 mb-2">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} required={required} maxLength={maxLength} disabled={disabled}
        className="w-full px-4 py-3.5 rounded-2xl border border-slate-200 bg-slate-50/50
                 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 focus:bg-white
                 outline-none transition-all text-sm text-slate-700
                 placeholder:text-slate-400 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed" />
    </div>
  );
}
