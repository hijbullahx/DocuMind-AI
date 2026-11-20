import React from 'react'
import {
  AlertTriangle,
  Check,
  Edit2,
  HelpCircle,
  Table,
  XCircle,
} from 'lucide-react'
import type { ReconciliationMatrixRow, ReconciliationRecord } from '@/types/reconciliation'

export interface FieldComparisonMatrixProps {
  record: ReconciliationRecord
  className?: string
}

export const FieldComparisonMatrix: React.FC<FieldComparisonMatrixProps> = ({
  record,
  className = '',
}) => {
  const matrix: ReconciliationMatrixRow[] = record.comparison_matrix || []
  const docAName = record.doc_a_details?.filename || 'Document A'
  const docBName = record.doc_b_details?.filename || 'Document B'

  if (matrix.length === 0) {
    return (
      <div className={`p-8 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800 ${className}`}>
        No comparison matrix generated.
      </div>
    )
  }

  const renderStatusBadge = (status: ReconciliationMatrixRow['status'], diff: string | null) => {
    switch (status) {
      case 'MATCH':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800">
            <Check className="w-3 h-3 text-emerald-400" />
            <span>Match</span>
          </span>
        )
      case 'DISCREPANCY':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-950/80 text-rose-300 border border-rose-800">
            <XCircle className="w-3 h-3 text-rose-400" />
            <span>Diff: {diff || 'Mismatch'}</span>
          </span>
        )
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/80 text-amber-300 border border-amber-800">
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            <span>Warning</span>
          </span>
        )
      case 'MISSING':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            <HelpCircle className="w-3 h-3 text-slate-500" />
            <span>Missing</span>
          </span>
        )
    }
  }

  const renderValueCell = (
    value: string | null,
    isCorrected: boolean,
    originalValue: string | null
  ) => {
    return (
      <div className="space-y-1">
        <div className="text-slate-100 font-medium font-mono text-xs truncate max-w-xs" title={value || '—'}>
          {value || <span className="text-slate-600">—</span>}
        </div>

        {/* Provenance: Indicate human manual correction */}
        {isCorrected && (
          <div className="flex items-center gap-1 text-[10px] font-mono text-amber-300/90 bg-amber-950/40 border border-amber-900/50 px-1.5 py-0.5 rounded w-fit">
            <Edit2 className="w-2.5 h-2.5 text-amber-400" />
            <span className="font-semibold">Human Edited</span>
            {originalValue && (
              <span className="text-slate-400 line-through ml-1">
                (AI: {originalValue})
              </span>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between pb-1">
        <div className="flex items-center gap-2">
          <Table className="w-4 h-4 text-emerald-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Header Entity Variance Matrix
          </h4>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          {matrix.length} fields audited
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/70 shadow-xs">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/90 text-slate-400 uppercase tracking-wider text-[10px] font-semibold">
              <th className="py-2.5 px-3 w-40">Financial Entity</th>
              <th className="py-2.5 px-3 min-w-[200px]">
                <div className="truncate text-blue-300 font-medium">Doc A: {docAName}</div>
              </th>
              <th className="py-2.5 px-3 min-w-[200px]">
                <div className="truncate text-emerald-300 font-medium">Doc B: {docBName}</div>
              </th>
              <th className="py-2.5 px-3 text-center w-36">Variance Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {matrix.map((row) => (
              <tr key={row.field} className="hover:bg-slate-900/50 transition-colors">
                <td className="py-3 px-3 font-medium text-slate-300 text-xs">
                  <div>{row.label}</div>
                  <div className="text-[10px] text-slate-500 font-mono">{row.field}</div>
                </td>
                <td className="py-3 px-3">
                  {renderValueCell(row.doc_a_value, row.doc_a_is_corrected, row.doc_a_original)}
                </td>
                <td className="py-3 px-3">
                  {renderValueCell(row.doc_b_value, row.doc_b_is_corrected, row.doc_b_original)}
                </td>
                <td className="py-3 px-3 text-center">
                  {renderStatusBadge(row.status, row.difference)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
