import React from 'react'
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

export type ToastType = 'info' | 'success' | 'warning' | 'danger'

export interface ToastProps {
  id?: string
  title?: string
  message: string
  type?: ToastType
  onClose: () => void
}

export const Toast: React.FC<ToastProps> = ({
  title,
  message,
  type = 'info',
  onClose,
}) => {
  const styles = {
    info: {
      bg: 'bg-slate-900 border-slate-700 text-slate-200',
      icon: <Info className="w-4 h-4 text-brand-400 shrink-0" />,
    },
    success: {
      bg: 'bg-emerald-950/90 border-emerald-800 text-emerald-200',
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
    },
    warning: {
      bg: 'bg-amber-950/90 border-amber-800 text-amber-200',
      icon: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />,
    },
    danger: {
      bg: 'bg-rose-950/90 border-rose-800 text-rose-200',
      icon: <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />,
    },
  }

  const currentStyle = styles[type]

  return (
    <div
      className={`flex items-start gap-3 p-3.5 rounded-xl border shadow-lg backdrop-blur-md transition-all animate-in fade-in slide-in-from-top-2 ${currentStyle.bg}`}
    >
      <div className="mt-0.5">{currentStyle.icon}</div>
      <div className="flex-1 text-xs space-y-0.5">
        {title && <div className="font-semibold">{title}</div>}
        <div className="text-slate-300 leading-relaxed">{message}</div>
      </div>
      <button
        onClick={onClose}
        className="text-slate-400 hover:text-slate-200 p-1 rounded-lg transition-colors"
        title="Dismiss alert"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
