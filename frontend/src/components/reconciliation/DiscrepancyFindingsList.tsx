import React, { useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Filter,
  Layers,
} from 'lucide-react'
import type { CrossDocumentDiscrepancy } from '@/types/reconciliation'

export interface DiscrepancyFindingsListProps {
  discrepancies: CrossDocumentDiscrepancy[]
  warnings: CrossDocumentDiscrepancy[]
  className?: string
}

type SeverityFilter = 'ALL' | 'ERRORS' | 'WARNINGS'

export const DiscrepancyFindingsList: React.FC<DiscrepancyFindingsListProps> = ({
  discrepancies = [],
  warnings = [],
  className = '',
}) => {
  const [filter, setFilter] = useState<SeverityFilter>('ALL')

  const totalErrors = discrepancies.length
  const totalWarnings = warnings.length
  const totalIssues = totalErrors + totalWarnings

  const filteredItems = [
    ...(filter !== 'WARNINGS' ? discrepancies : []),
    ...(filter !== 'ERRORS' ? warnings : []),
  ]

  const getRuleBadgeColor = (ruleId: string) => {
    switch (ruleId) {
      case 'CROSS_POTENTIAL_DUPLICATE':
        return 'bg-purple-950/80 text-purple-300 border-purple-800/50'
      case 'CROSS_TOTAL_MISMATCH':
      case 'CROSS_SUBTOTAL_MISMATCH':
      case 'CROSS_TAX_MISMATCH':
        return 'bg-rose-950/80 text-rose-300 border-rose-800/50'
      case 'CROSS_SUPPLIER_MISMATCH':
      case 'CROSS_CUSTOMER_MISMATCH':
      case 'CROSS_REFERENCE_MISMATCH':
      case 'CROSS_DATE_MISMATCH':
        return 'bg-amber-950/80 text-amber-300 border-amber-800/50'
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700'
    }
  }

  if (totalIssues === 0) {
    return (
      <div className={`bg-slate-900 border border-slate-800 rounded-xl p-8 text-center ${className}`}>
        <div className="w-12 h-12 bg-emerald-950/60 border border-emerald-800/40 rounded-full flex items-center justify-center mx-auto mb-3">
          <CheckCircle2 className="w-6 h-6 text-emerald-400" />
        </div>
        <h4 className="text-base font-bold text-slate-100">Clean Reconciliation Audit</h4>
        <p className="text-xs text-slate-400 mt-1.5 max-w-md mx-auto">
          No cross-document discrepancies or variance warnings were detected between the compared documents within the configured tolerance threshold.
        </p>
      </div>
    )
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center gap-2.5">
          <Layers className="w-5 h-5 text-brand-400" />
          <h3 className="text-sm font-bold text-slate-200">
            Reconciliation Findings & Discrepancies
          </h3>
          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-800 text-slate-300">
            {totalIssues} issue{totalIssues === 1 ? '' : 's'}
          </span>
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
          <span className="flex items-center gap-1 text-slate-400 px-2">
            <Filter className="w-3.5 h-3.5" /> Severity:
          </span>
          <button
            onClick={() => setFilter('ALL')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filter === 'ALL'
                ? 'bg-slate-800 text-brand-300'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({totalIssues})
          </button>
          <button
            onClick={() => setFilter('ERRORS')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filter === 'ERRORS'
                ? 'bg-rose-950/80 text-rose-300 border border-rose-800/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Errors ({totalErrors})
          </button>
          <button
            onClick={() => setFilter('WARNINGS')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filter === 'WARNINGS'
                ? 'bg-amber-950/80 text-amber-300 border border-amber-800/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Warnings ({totalWarnings})
          </button>
        </div>
      </div>

      {/* Cards list */}
      <div className="space-y-3">
        {filteredItems.map((issue, idx) => {
          const isError = issue.severity === 'ERROR'
          const ruleBadgeClass = getRuleBadgeColor(issue.rule_id)

          return (
            <div
              key={`${issue.rule_id}-${issue.field}-${idx}`}
              className={`rounded-xl border p-4 transition-all ${
                isError
                  ? 'bg-rose-950/15 border-rose-900/40 hover:border-rose-700/60'
                  : 'bg-amber-950/15 border-amber-900/40 hover:border-amber-700/60'
              }`}
            >
              {/* Card top row */}
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  {isError ? (
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  )}
                  <span
                    className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded border ${
                      isError
                        ? 'bg-rose-900/40 text-rose-300 border-rose-700/50'
                        : 'bg-amber-900/40 text-amber-300 border-amber-700/50'
                    }`}
                  >
                    {issue.severity}
                  </span>
                  <span
                    className={`text-[11px] font-mono px-2 py-0.5 rounded border ${ruleBadgeClass}`}
                  >
                    {issue.rule_id}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    target: <span className="text-slate-200 font-semibold">{issue.field}</span>
                  </span>
                </div>

                {issue.difference != null && (
                  <span className="text-xs font-mono font-semibold text-rose-300 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800/40">
                    Δ Variance: {String(issue.difference)}
                  </span>
                )}
              </div>

              {/* Message text */}
              <p className="text-xs text-slate-300 font-medium leading-relaxed mb-3">
                {issue.message}
              </p>

              {/* Value comparison drawer */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2.5 border-t border-slate-800/80">
                <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
                  <div className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider mb-1 flex items-center justify-between">
                    <span>Document A Value</span>
                    <span className="font-mono text-[9px] text-slate-500">{issue.doc_a_id.slice(0, 8)}</span>
                  </div>
                  <div className="text-xs font-mono text-slate-100 break-words">
                    {issue.doc_a_value || <span className="text-slate-500 italic">None / Missing</span>}
                  </div>
                </div>

                <div className="bg-slate-900/90 rounded-lg p-2.5 border border-slate-800">
                  <div className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider mb-1 flex items-center justify-between">
                    <span>Document B Value</span>
                    <span className="font-mono text-[9px] text-slate-500">{issue.doc_b_id.slice(0, 8)}</span>
                  </div>
                  <div className="text-xs font-mono text-slate-100 break-words">
                    {issue.doc_b_value || <span className="text-slate-500 italic">None / Missing</span>}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
