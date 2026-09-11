import React from 'react';
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

interface ToastProps {
  toast: ToastMessage | null;
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ toast, onClose }) => {
  if (!toast) return null;

  const typeConfig = {
    success: {
      bg: 'bg-emerald-50 border-emerald-200 text-emerald-800',
      icon: <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />,
    },
    error: {
      bg: 'bg-rose-50 border-rose-200 text-rose-800',
      icon: <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />,
    },
    warning: {
      bg: 'bg-amber-50 border-amber-200 text-amber-800',
      icon: <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />,
    },
    info: {
      bg: 'bg-sky-50 border-sky-200 text-sky-800',
      icon: <Info className="w-5 h-5 text-sky-600 flex-shrink-0" />,
    },
  };

  const config = typeConfig[toast.type];

  return (
    <div className="fixed top-5 right-5 z-50 max-w-md w-full animate-in fade-in slide-in-from-top-4 duration-200">
      <div className={`flex items-start p-4 rounded-xl border shadow-lg ${config.bg}`}>
        <div className="mr-3 mt-0.5">{config.icon}</div>
        <div className="flex-1 text-sm font-medium">{toast.message}</div>
        <button
          onClick={onClose}
          className="ml-3 text-gray-400 hover:text-gray-600 p-1 rounded-lg"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
