import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

const VARIANTS = {
  success: {
    icon: CheckCircle2,
    bar: 'bg-emerald-500',
    bg: 'bg-white border-emerald-200',
    text: 'text-emerald-800',
    iconColor: 'text-emerald-500',
  },
  error: {
    icon: AlertCircle,
    bar: 'bg-red-500',
    bg: 'bg-white border-red-200',
    text: 'text-red-800',
    iconColor: 'text-red-500',
  },
  info: {
    icon: Info,
    bar: 'bg-indigo-500',
    bg: 'bg-white border-indigo-200',
    text: 'text-indigo-800',
    iconColor: 'text-indigo-500',
  },
};

export default function Toast({ message, variant = 'info', onClose, duration = 4500 }) {
  const style = VARIANTS[variant] || VARIANTS.info;
  const Icon = style.icon;

  useEffect(() => {
    if (!message || !onClose) return undefined;
    const timer = window.setTimeout(onClose, duration);
    return () => window.clearTimeout(timer);
  }, [message, onClose, duration]);

  if (!message) return null;

  return createPortal(
    <div
      className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] w-[min(92vw,420px)] pointer-events-none"
      role="status"
      aria-live="polite"
    >
      <div
        className={`pointer-events-auto flex items-start gap-3 rounded-xl border shadow-lg px-4 py-3 ${style.bg}`}
      >
        <div className={`w-1 self-stretch rounded-full shrink-0 ${style.bar}`} />
        <Icon size={20} className={`shrink-0 mt-0.5 ${style.iconColor}`} />
        <p className={`flex-1 text-sm font-medium leading-snug ${style.text}`}>{message}</p>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          aria-label="Cerrar notificación"
        >
          <X size={16} />
        </button>
      </div>
    </div>,
    document.body,
  );
}
