import { createPortal } from 'react-dom';
import { Download, Printer, X } from 'lucide-react';

export default function DocumentViewerModal({ open, title, imageUrl, onClose, onDownload, onPrint }) {
  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative w-[95vw] max-w-4xl max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="font-semibold text-slate-700 truncate pr-4">{title || 'Vista previa de carta'}</h3>
          <div className="flex items-center gap-2">
            <button onClick={onDownload} className="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 flex items-center gap-2 text-sm">
              <Download size={16} /> Descargar
            </button>
            <button onClick={onPrint} className="px-3 py-2 rounded-lg bg-indigo-100 hover:bg-indigo-200 text-indigo-700 flex items-center gap-2 text-sm">
              <Printer size={16} /> Imprimir
            </button>
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="p-3 bg-slate-100 overflow-auto max-h-[calc(90vh-56px)]">
          <img src={imageUrl} alt={title || 'Carta'} className="mx-auto rounded-lg shadow bg-white max-w-full h-auto" />
        </div>
      </div>
    </div>,
    document.body,
  );
}
