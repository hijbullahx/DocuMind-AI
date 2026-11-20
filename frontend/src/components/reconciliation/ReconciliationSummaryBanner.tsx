import React from 'react'
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Layers,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatDateTime } from '@/utils/formatters'
import type { ReconciliationRecord } from '@/types/reconciliation'

export interface ReconciliationSummaryBannerProps {
  record: ReconciliationRecord
  isReReconciling?: boolean
  onReReconcile?: () => void
  className?: string
}

export const ReconciliationSummaryBanner: React.FC<ReconciliationSummaryBannerProps> = ({
  record,
  isReReconciling = false,
  onReReconcile,
  className = '',
}) => {
  const isVerified = record.status === 'VERIFIED'
  const isNeedsReview = record.status === 'NEEDS_REVIEW'

  const borderVariant = isVerified
    ? 'border-emerald-800/80 bg-emerald-950/20'
    : isNeedsReview
    ? 'border-amber-800/80 bg-amber-950/20'
    : 'border-rose-800/80 bg-rose-950/20'

  const badgeVariant = isVerified
    ? 'bg-emerald-950/90 text-emerald-300 border-emerald-800'
    : isNeedsReview
    ? 'bg-amber-950/90 text-amber-300 border-amber-800'
    : 'bg-rose-950/90 text-rose-300 border-rose-800'

  return (
    <div className={`p-4 sm:p-5 rounded-2xl border space-y-4 ${borderVariant} ${className}`}>
      {/* Top Banner Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`p-2.5 rounded-xl border ${
              isVerified
                ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                : isNeedsReview
                ? 'bg-amber-950 text-amber-400 border-amber-800'
                : 'bg-rose-950 text-rose-400 border-rose-800'
            }`}
          >
            {isVerified ? (
              <ShieldCheck className="w-6 h-6" />
            ) : isNeedsReview ? (
              <AlertTriangle className="w-6 h-6" />
            ) : (
              <ShieldAlert className="w-6 h-6" />
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border ${badgeVariant}`}>
                {record.status}
              </span>
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                <span>{formatDateTime(record.created_at)}</span>
              </span>
            </div>

            <h2 className="text-base sm:text-lg font-bold text-slate-100 pt-1">
              {isVerified
                ? 'Documents Fully Balanced & Reconciled'
                : isNeedsReview
                ? 'Cross-Reconciliation Requires Review'
                : 'Reconciliation Failed — Discrepancies Detected'}
            </h2>
          </div>
        </div>

        {/* Re-run Reconciliation Action */}
        {onReReconcile && (
          <Button
            variant="outline"
            size="sm"
            onClick={onReReconcile}
            isLoading={isReReconciling}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            className="text-xs"
          >
            Re-Reconcile
          </Button>
        )}
      </div>

      {/* Summary Narrative */}
      {record.summary && (
        <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
          {record.summary}
        </p>
      )}

      {/* 4 Reconciliation Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Critical Discrepancies */}
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-[11px] uppercase tracking-wider font-semibold">
            <span>Discrepancies</span>
            <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <div className={`text-xl font-mono font-extrabold ${record.discrepancies.length > 0 ? 'text-rose-400' : 'text-slate-300'}`}>
            {record.discrepancies.length}
          </div>
          <p className="text-[10px] text-slate-500">Critical financial variance</p>
        </div>

        {/* Review Warnings */}
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-[11px] uppercase tracking-wider font-semibold">
            <span>Warnings</span>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className={`text-xl font-mono font-extrabold ${record.warnings.length > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
            {record.warnings.length}
          </div>
          <p className="text-[10px] text-slate-500">Non-fatal review points</p>
        </div>

        {/* Matched Line Items */}
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-[11px] uppercase tracking-wider font-semibold">
            <span>Matched Items</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-mono font-extrabold text-emerald-400">
            {record.matched_items_count}
          </div>
          <p className="text-[10px] text-slate-500">Paired line-item rows</p>
        </div>

        {/* Unmatched Line Items */}
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-[11px] uppercase tracking-wider font-semibold">
            <span>Unmatched Items</span>
            <Layers className="w-3.5 h-3.5 text-slate-500" />
          </div>
          <div className={`text-xl font-mono font-extrabold ${record.unmatched_items_count > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
            {record.unmatched_items_count}
          </div>
          <p className="text-[10px] text-slate-500">Missing in one document</p>
        </div>
      </div>
    </div>
  )
}
