import React, { useState } from 'react'
import {
  X,
  History,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ArrowRight,
  Search,
  FileText,
} from 'lucide-react'
import type { ReconciliationRecord } from '@/types/reconciliation'

export interface ReconciliationHistoryDrawerProps {
  isOpen: boolean
  onClose: () => void
  history: ReconciliationRecord[]
  onSelectRecord: (id: string) => void
  currentRecordId?: string
  isLoading?: boolean
}

export const ReconciliationHistoryDrawer: React.FC<ReconciliationHistoryDrawerProps> = ({
  isOpen,
  onClose,
  history = [],
  onSelectRecord,
  currentRecordId,
  isLoading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState('')

  if (!isOpen) return null

  const filteredHistory = history.filter((rec) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    const docAName = rec.doc_a_details?.filename?.toLowerCase() || ''
    const docBName = rec.doc_b_details?.filename?.toLowerCase() || ''
    const status = rec.status.toLowerCase()
    const id = rec.id.toLowerCase()
    return (
      docAName.includes(term) ||
      docBName.includes(term) ||
      status.includes(term) ||
      id.includes(term)
    )
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />
      case 'NEEDS_REVIEW':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-rose-400" />
      default:
        return <Clock className="w-4 h-4 text-slate-400" />
    }
  }

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return 'bg-emerald-950/80 text-emerald-300 border-emerald-800/40'
      case 'NEEDS_REVIEW':
        return 'bg-amber-950/80 text-amber-300 border-amber-800/40'
      case 'FAILED':
        return 'bg-rose-950/80 text-rose-300 border-rose-800/40'
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700'
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer content */}
      <div className="relative w-full max-w-md bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl z-10">
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-2.5">
            <History className="w-5 h-5 text-brand-400" />
            <div>
              <h3 className="text-sm font-bold text-slate-200">Reconciliation History</h3>
              <p className="text-[11px] text-slate-500">
                {history.length} past audit session{history.length === 1 ? '' : 's'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Bar */}
        <div className="p-3 border-b border-slate-800/80 bg-slate-900/60">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter by document name or status..."
              className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/60"
            />
          </div>
        </div>

        {/* List of sessions */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
          {isLoading ? (
            <div className="p-8 text-center text-xs text-slate-500">
              Loading past reconciliation records...
            </div>
          ) : filteredHistory.length === 0 ? (
            <div className="p-8 text-center">
              <FileText className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-400 font-medium">No past sessions found</p>
              <p className="text-[11px] text-slate-600 mt-0.5">
                Execute a reconciliation to record results here.
              </p>
            </div>
          ) : (
            filteredHistory.map((rec) => {
              const isSelected = rec.id === currentRecordId
              const docAName = rec.doc_a_details?.filename || rec.doc_a.slice(0, 8)
              const docBName = rec.doc_b_details?.filename || rec.doc_b.slice(0, 8)
              const formattedDate = new Date(rec.created_at).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })

              return (
                <div
                  key={rec.id}
                  onClick={() => {
                    onSelectRecord(rec.id)
                    onClose()
                  }}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-brand-950/40 border-brand-500/50 shadow-sm shadow-brand-500/10 ring-1 ring-brand-500/30'
                      : 'bg-slate-950/60 border-slate-800 hover:bg-slate-800/40 hover:border-slate-700'
                  }`}
                >
                  {/* Top row: Status & Timestamp */}
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${getStatusBadgeClass(
                        rec.status
                      )}`}
                    >
                      {getStatusIcon(rec.status)}
                      {rec.status.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">{formattedDate}</span>
                  </div>

                  {/* Document pairing */}
                  <div className="space-y-1 mb-2.5">
                    <div className="text-xs font-semibold text-slate-200 truncate flex items-center gap-1.5">
                      <span className="text-[10px] px-1 bg-slate-800 text-slate-400 rounded">A</span>
                      <span className="truncate">{docAName}</span>
                    </div>
                    <div className="text-xs font-semibold text-slate-200 truncate flex items-center gap-1.5">
                      <span className="text-[10px] px-1 bg-slate-800 text-slate-400 rounded">B</span>
                      <span className="truncate">{docBName}</span>
                    </div>
                  </div>

                  {/* Discrepancies and stats footer */}
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800/60">
                    <div className="flex items-center gap-2">
                      <span
                        className={
                          rec.discrepancies.length > 0
                            ? 'text-rose-400 font-semibold'
                            : 'text-slate-500'
                        }
                      >
                        {rec.discrepancies.length} error{rec.discrepancies.length === 1 ? '' : 's'}
                      </span>
                      <span>•</span>
                      <span
                        className={
                          rec.warnings.length > 0
                            ? 'text-amber-400 font-semibold'
                            : 'text-slate-500'
                        }
                      >
                        {rec.warnings.length} warning{rec.warnings.length === 1 ? '' : 's'}
                      </span>
                    </div>

                    <span className="flex items-center gap-1 text-brand-400 text-[11px] font-medium group-hover:underline">
                      Load <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
