import { useState, useEffect, useLayoutEffect, useCallback, memo } from 'react';
import { useAuth } from './hooks/useAuth';
import { signOut } from 'firebase/auth';
import { auth } from './services/firebase';
import { gpsTracking } from './services/gpsTracking';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AdminPage from './pages/AdminPage';
import StatsPage from './pages/StatsPage';
import TrackingPage from './pages/TrackingPage';
import MapRoutePage from './pages/MapRoutePage';
import RoutePlanPage from './pages/RoutePlanPage';
import GestorStatsPage from './pages/GestorStatsPage';
import {
  Settings, LayoutDashboard, LogOut, Menu, X, Shield, BarChart3, Navigation, Bell,
  MapPin, Route, TrendingUp
} from 'lucide-react';
import NotificationBell from './components/NotificationBell';

export default function App() {
  const { user, userData, loading } = useAuth();
  const [view, setView] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useCallback((v) => { setView(v); setSidebarOpen(false); }, []);

  // ── Reset scroll position on every view change (before browser paint) ──
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [view]);

  // ── Start/stop GPS tracking based on auth state ──
  useEffect(() => {
    if (user && userData) {
      // Start continuous GPS tracking for this session
      if (!gpsTracking.isRunning) {
        gpsTracking.start({
          seccion: userData.seccion || '',
          gestorName: userData.nombre || user.email || '',
        });
      }
    } else {
      // Stop tracking when logged out
      if (gpsTracking.isRunning) {
        gpsTracking.stop();
      }
    }
    return () => {
      // Cleanup on unmount
      if (gpsTracking.isRunning) gpsTracking.stop();
    };
  }, [user, userData]);

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="w-9 h-9 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Cargando...</p>
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  if (view === 'admin') {
    return <AdminPage onBack={() => setView('dashboard')} />;
  }

  if (view === 'tracking') {
    return <TrackingPage onBack={() => setView('dashboard')} />;
  }

  if (view === 'maproute') {
    return <MapRoutePage user={user} userData={userData} onBack={() => setView('dashboard')} />;
  }

  if (view === 'routeplan') {
    const adminRole = userData?.rol === 'admin' || userData?.rol === 'supervisor';
    return <RoutePlanPage user={user} userData={userData} onBack={() => setView('dashboard')} isAdmin={adminRole} />;
  }

  if (view === 'gestorstats') {
    return <GestorStatsPage user={user} userData={userData} onBack={() => setView('dashboard')} />;
  }

  if (view === 'stats') {
    // Stats page uses the full sidebar layout below
  }

  const isAdmin = userData?.rol === 'admin' || userData?.rol === 'supervisor';
  const isAsistente = userData?.rol === 'asistente';
  const seccion = userData?.seccion || '';

  // Derive geo context from secciones (composite keys like '01_1211_H')
  const secciones = userData?.secciones || [];
  const geoLabel = (() => {
    const validKeys = secciones.filter(k => typeof k === 'string' && k.includes('_'));
    if (validKeys.length === 0) {
      if (userData?.region && userData?.zona && seccion) {
        return `R${userData.region} · Z${userData.zona} · Sección ${seccion}`;
      }
      return seccion ? `Sección ${seccion}` : '';
    }
    if (validKeys.length === 1) {
      const [r, z, s] = validKeys[0].split('_');
      return `R${r} · Z${z} · Sección ${s}`;
    }
    // Multiple sections: group by region
    const regions = [...new Set(validKeys.map(k => k.split('_')[0]))];
    if (regions.length === 1) {
      const letters = validKeys.map(k => k.split('_')[2]).join(', ');
      return `R${regions[0]} · Secciones ${letters}`;
    }
    return `${validKeys.length} secciones (${regions.length} regiones)`;
  })();
  const nombre = userData?.nombre || user?.displayName || user?.email || '';
  const email = user?.email || '';
  const initials = nombre
    .split(' ')
    .filter(Boolean)
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || '?';

  return (
    <div className="min-h-screen bg-slate-100/70 flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/30 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:sticky lg:top-0 h-screen w-[292px] bg-white border-r border-slate-200
        z-50 flex flex-col shrink-0 transition-transform duration-200 ease-out shadow-sm lg:shadow-none
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Brand */}
        <div className="h-16 flex items-center gap-2.5 px-5 border-b border-slate-100 shrink-0">
          <Shield size={22} className="text-indigo-600" />
          <span className="text-lg font-bold text-gray-900 tracking-tight">AntCobranzas</span>
          <button onClick={() => setSidebarOpen(false)} className="ml-auto p-1.5 hover:bg-gray-100 rounded-lg lg:hidden">
            <X size={18} className="text-gray-400" />
          </button>
        </div>

        {/* Profile card */}
        <div className="px-4 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-semibold shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-gray-900 text-sm truncate">{nombre}</p>
              <p className="text-xs text-gray-500 truncate">{email}</p>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {isAdmin ? (
              <span className="text-xs bg-purple-50 text-purple-700 px-2.5 py-1 rounded-md font-medium">
                Administrador
              </span>
            ) : geoLabel ? (
              <span className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-md font-medium">
                {geoLabel}
              </span>
            ) : (
              <span className="text-xs bg-amber-50 text-amber-700 px-2.5 py-1 rounded-md font-medium">
                Sin sección asignada
              </span>
            )}
            {!isAdmin && (
              <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-md font-medium capitalize">
                {userData?.rol || 'gestor'}
              </span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3.5 space-y-1.5 overflow-y-auto">
          <SidebarItem
            icon={<LayoutDashboard size={20} />}
            label="Dashboard"
            active={view === 'dashboard'}
            onClick={() => navigate('dashboard')}
          />
          <SidebarItem
            icon={<MapPin size={20} />}
            label="Mapa de Clientes"
            active={view === 'maproute'}
            onClick={() => navigate('maproute')}
          />
          {!isAdmin && (
            <SidebarItem
              icon={<Route size={20} />}
              label="Mis Rutas"
              active={view === 'routeplan'}
              onClick={() => navigate('routeplan')}
            />
          )}
          {(isAdmin || isAsistente) && (
            <SidebarItem
              icon={<BarChart3 size={20} />}
              label="Estadísticas"
              active={view === 'stats'}
              onClick={() => navigate('stats')}
            />
          )}
          {isAdmin && (
            <SidebarItem
              icon={<TrendingUp size={20} />}
              label="Métricas Gestores"
              active={view === 'gestorstats'}
              onClick={() => navigate('gestorstats')}
            />
          )}
          {isAdmin && (
            <SidebarItem
              icon={<Navigation size={20} />}
              label="Rastreo GPS"
              active={view === 'tracking'}
              onClick={() => navigate('tracking')}
            />
          )}
          {isAdmin && (
            <SidebarItem
              icon={<Settings size={20} />}
              label="Administración"
              active={view === 'admin'}
              onClick={() => navigate('admin')}
            />
          )}
        </nav>

        {/* Logout */}
        <div className="p-3.5 border-t border-slate-100 shrink-0">
          <div className="flex items-center justify-between px-3 mb-2">
            <NotificationBell uid={user?.uid} />
          </div>
          <button
            onClick={() => signOut(auth)}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-gray-600
                     hover:text-red-600 hover:bg-red-50 rounded-lg transition-all font-medium"
          >
            <LogOut size={20} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 h-14 bg-white border-b border-slate-200 flex items-center px-4 gap-3 lg:hidden shrink-0">
          <button onClick={() => setSidebarOpen(true)} className="p-2 -ml-2 hover:bg-gray-100 rounded-lg">
            <Menu size={20} className="text-gray-600" />
          </button>
          <span className="text-base font-bold text-gray-900">AntCobranzas</span>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell uid={user?.uid} />
            {!isAdmin && geoLabel && (
              <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-medium truncate max-w-[180px]">
                {geoLabel}
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main key={view} className="flex-1 lg:p-5 page-enter">
          {view === 'stats'
            ? <StatsPage user={user} userData={userData} />
            : <DashboardPage user={user} userData={userData} />
          }
        </main>
      </div>
    </div>
  );
}

const SidebarItem = memo(function SidebarItem({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
        ${active
          ? 'bg-indigo-50 text-indigo-700 shadow-sm border border-indigo-100'
          : 'text-gray-600 hover:bg-slate-50 hover:text-gray-900 border border-transparent hover:border-slate-100'
        }`}
    >
      {icon}
      {label}
    </button>
  );
});
