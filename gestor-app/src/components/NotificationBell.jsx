import { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Bell, X, ChevronDown, ChevronUp, Check, UserPlus, RefreshCw, UserMinus } from 'lucide-react';
import { subscribeNotifications, markAsRead } from '../services/notificationService';

const PANEL_WIDTH = 384;
const VIEWPORT_MARGIN = 8;
const GAP = 8;

function computePanelStyle(anchorRect) {
  const width = Math.min(PANEL_WIDTH, window.innerWidth - VIEWPORT_MARGIN * 2);
  const maxHeight = Math.min(
    window.innerHeight * 0.7,
    window.innerHeight - VIEWPORT_MARGIN * 2,
  );

  let left = anchorRect.left;
  if (left + width > window.innerWidth - VIEWPORT_MARGIN) {
    left = window.innerWidth - width - VIEWPORT_MARGIN;
  }
  left = Math.max(VIEWPORT_MARGIN, left);

  const spaceBelow = window.innerHeight - anchorRect.bottom - VIEWPORT_MARGIN;
  const spaceAbove = anchorRect.top - VIEWPORT_MARGIN;
  const openUpward = spaceBelow < 240 && spaceAbove > spaceBelow;

  if (openUpward) {
    return {
      position: 'fixed',
      bottom: window.innerHeight - anchorRect.top + GAP,
      left,
      width,
      maxHeight: Math.min(maxHeight, spaceAbove - GAP),
      zIndex: 100,
    };
  }

  return {
    position: 'fixed',
    top: anchorRect.bottom + GAP,
    left,
    width,
    maxHeight: Math.min(maxHeight, spaceBelow - GAP),
    zIndex: 100,
  };
}

/**
 * NotificationBell — Icon with unread badge + dropdown panel.
 * Place in sidebar or top bar. Receives user UID and an optional
 * onRefreshClients callback to trigger client data reload.
 */
export default function NotificationBell({ uid, onRefreshClients }) {
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [panelStyle, setPanelStyle] = useState(null);
  const rootRef = useRef(null);
  const panelRef = useRef(null);
  const buttonRef = useRef(null);

  const unreadCount = notifications.filter((n) => !n.leida).length;

  const updatePanelPosition = useCallback(() => {
    if (!buttonRef.current) return;
    setPanelStyle(computePanelStyle(buttonRef.current.getBoundingClientRect()));
  }, []);

  // Subscribe to real-time notifications
  useEffect(() => {
    if (!uid) return;
    const unsub = subscribeNotifications(uid, setNotifications);
    return unsub;
  }, [uid]);

  useLayoutEffect(() => {
    if (!open) {
      setPanelStyle(null);
      return undefined;
    }

    updatePanelPosition();

    const handleReposition = () => updatePanelPosition();
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);

    return () => {
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [open, updatePanelPosition]);

  // Close panel on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      const inTrigger = rootRef.current?.contains(e.target);
      const inPanel = panelRef.current?.contains(e.target);
      if (!inTrigger && !inPanel) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleOpen = () => {
    setOpen((prev) => !prev);
  };

  const handleMarkRead = async (notifId, e) => {
    e.stopPropagation();
    await markAsRead(notifId);
  };

  const handleExpand = (notifId) => {
    setExpandedId(expandedId === notifId ? null : notifId);
  };

  const tipoIcon = (tipo) => {
    switch (tipo) {
      case 'nuevo': return <UserPlus size={14} className="text-emerald-600 shrink-0" />;
      case 'actualizado': return <RefreshCw size={14} className="text-blue-600 shrink-0" />;
      case 'removido': return <UserMinus size={14} className="text-red-500 shrink-0" />;
      default: return null;
    }
  };

  const panel = open && panelStyle && createPortal(
    <div
      ref={panelRef}
      style={panelStyle}
      className="bg-white border border-slate-200 rounded-xl shadow-xl flex flex-col overflow-hidden"
      role="dialog"
      aria-label="Notificaciones"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
        <h3 className="font-semibold text-gray-900 text-sm">Notificaciones</h3>
        <button onClick={() => setOpen(false)} className="p-1 hover:bg-slate-100 rounded-lg">
          <X size={16} className="text-gray-400" />
        </button>
      </div>

      {/* List */}
      <div className="overflow-y-auto flex-1 min-h-0">
        {notifications.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Bell size={32} className="text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No hay notificaciones</p>
          </div>
        ) : (
          notifications.map((notif) => (
            <div
              key={notif.id}
              className={`border-b border-slate-50 last:border-b-0 ${
                notif.leida ? 'bg-white' : 'bg-indigo-50/40'
              }`}
            >
              {/* Notification header */}
              <div
                className="px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => handleExpand(notif.id)}
              >
                <div className="flex items-start gap-2">
                  <div className="w-2 h-2 rounded-full mt-1.5 shrink-0" style={{
                    backgroundColor: notif.leida ? 'transparent' : '#6366f1'
                  }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{notif.titulo}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{notif.mensaje}</p>
                    <p className="text-xs text-gray-400 mt-1">{notif.fecha_str}</p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {!notif.leida && (
                      <button
                        onClick={(e) => handleMarkRead(notif.id, e)}
                        className="p-1 hover:bg-indigo-100 rounded text-indigo-600"
                        title="Marcar como leída"
                      >
                        <Check size={14} />
                      </button>
                    )}
                    {expandedId === notif.id
                      ? <ChevronUp size={16} className="text-gray-400" />
                      : <ChevronDown size={16} className="text-gray-400" />
                    }
                  </div>
                </div>
              </div>

              {/* Expanded details */}
              {expandedId === notif.id && notif.detalles && (
                <div className="px-4 pb-3">
                  <div className="bg-slate-50 rounded-lg p-3 space-y-2">
                    {notif.detalles.map((det, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        {tipoIcon(det.tipo)}
                        <div className="min-w-0 flex-1">
                          <span className="font-medium text-gray-800">{det.nombre}</span>
                          <span className="text-gray-500 ml-1">({det.codigo_cliente})</span>
                          <p className="text-gray-600 mt-0.5">{det.mensaje}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {onRefreshClients && (
                    <button
                      onClick={() => { onRefreshClients(); setOpen(false); }}
                      className="mt-2 w-full py-2 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors flex items-center justify-center gap-1.5"
                    >
                      <RefreshCw size={13} />
                      Actualizar datos de clientes
                    </button>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>,
    document.body,
  );

  return (
    <div className="relative" ref={rootRef}>
      {/* Bell button */}
      <button
        ref={buttonRef}
        onClick={handleOpen}
        className="relative p-2 hover:bg-slate-100 rounded-lg transition-colors"
        title="Notificaciones"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Bell size={20} className="text-gray-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center ring-2 ring-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {panel}
    </div>
  );
}
