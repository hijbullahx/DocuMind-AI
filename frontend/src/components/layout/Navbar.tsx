import React from 'react'
import {
  FileText,
  RefreshCw,
  Server,
  ShieldCheck,
  User,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'

export interface NavbarProps {
  backendConnected: boolean
  isCheckingBackend: boolean
  onRefreshMetrics: () => void
  onToggleSidebar?: () => void
}

export const Navbar: React.FC<NavbarProps> = ({
  backendConnected,
  isCheckingBackend,
  onRefreshMetrics,
}) => {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/95 backdrop-blur-sm sticky top-0 z-30 px-4 sm:px-6 flex items-center justify-between">
      {/* Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-brand-500/20 ring-1 ring-brand-400/30">
          <FileText className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-bold tracking-tight text-white">
              DocuMind<span className="text-brand-400">-AI</span>
            </span>
            <span className="text-[10px] font-semibold bg-brand-950 text-brand-300 border border-brand-800/80 px-1.5 py-0.5 rounded uppercase tracking-wider">
              v1.0
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium hidden sm:block">
            Enterprise Document Intelligence & Financial Validation
          </p>
        </div>
      </div>

      {/* Right Actions & Operator Status */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Backend Connectivity Status Pill */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium transition-colors ${
            backendConnected
              ? 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
              : 'bg-rose-950/60 border-rose-800/80 text-rose-300'
          }`}
          title={
            backendConnected
              ? 'Django REST API is live and responding'
              : 'Django REST API unreachable at /api'
          }
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              backendConnected
                ? 'bg-emerald-400 animate-pulse'
                : 'bg-rose-400'
            }`}
          />
          <Server className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">
            {backendConnected ? 'Backend Live' : 'Backend Offline'}
          </span>
        </div>

        {/* Refresh Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={onRefreshMetrics}
          isLoading={isCheckingBackend}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isCheckingBackend ? 'animate-spin' : ''}`} />}
          title="Refresh metrics and server health"
        >
          <span className="hidden sm:inline">Refresh</span>
        </Button>

        {/* Operator Profile */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
            <User className="w-4 h-4" />
          </div>
          <div className="hidden md:block text-left">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-slate-200">
                Auditor Session
              </span>
              <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
            </div>
            <span className="text-[10px] text-slate-400">Compliance Operator</span>
          </div>
        </div>
      </div>
    </header>
  )
}
