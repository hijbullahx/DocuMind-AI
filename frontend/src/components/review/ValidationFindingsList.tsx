import React, { useState } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle, Info, ShieldAlert, User } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { formatDateTime } from '@/utils/formatters'
import type { ValidationError, ValidationSeverity } from '@/types/document'

export interface ValidationFindingsListProps {
  findings: ValidationError[]
  className?: string
}

export const ValidationFindingsList: React.FC<ValidationFindingsListProps> = ({
  findings,
  className = '',
}) => {
  const [filterSeverity, setFilterSeverity] = useState<'ALL' | ValidationSeverity>('ALL')

  const errorCount = findings.filter((f) => f.severity === 'ERROR').length
  const warningCount = findings.filter((f) => f.severity === 'WARNING').length
  const infoCount = findings.filter((f) => f.severity === 'INFO').length

  const filteredFindings = findings.filter((f) => {
    if (filterSeverity === 'ALL') return true
    return f.severity === filterSeverity
  })

  if (findings.length === 0) {
    return (
      <div className={`p-8 text-center space-y-3 bg-emerald-950/20 border border-emerald-900/40 rounded-xl ${className}`}>
        <div className="w-12 h-12 rounded-full bg-emerald-900/40 border border-emerald-800/80 flex items-center justify-center mx-auto text-emerald-400">
          <CheckCircle className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h4 className="text-sm font-semibold text-emerald-200">
            All Deterministic Validation Rules Passed
          </h4>
          <p className="text-xs text-emerald-300/70 max-w-md mx-auto">
            Zero mathematical discrepancies, anomaly flags, or cross-field inconsistencies were detected on this document.
          </p>
        </div>
      </div>
    )
  }

  const getSeverityIcon = (sev: ValidationSeverity) => {
    switch (sev) {
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
      case 'INFO':
        return <Info className="w-4 h-4 text-blue-400 shrink-0" />
    }
  }

  const getCardBorder = (sev: ValidationSeverity) => {
    switch (sev) {
      case 'ERROR':
        return 'border-rose-900/60 bg-rose-950/20 hover:border-rose-800/80'
      case 'WARNING':
        return 'border-amber-900/60 bg-amber-950/20 hover:border-amber-800/80'
      case 'INFO':
        return 'border-blue-900/60 bg-blue-950/20 hover:border-blue-800/80'
    }
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header and filter controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-slate-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Validation Findings ({findings.length})
          </h4>
        </div>

        <div className="flex items-center gap-1 bg-slate-900 p-0.5 rounded-lg border border-slate-800 text-xs">
          <button
            type="button"
            onClick={() => setFilterSeverity('ALL')}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              filterSeverity === 'ALL'
                ? 'bg-slate-800 text-white shadow-xs'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({findings.length})
          </button>
          {errorCount > 0 && (
            <button
              type="button"
              onClick={() => setFilterSeverity('ERROR')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
                filterSeverity === 'ERROR'
                  ? 'bg-rose-950/80 text-rose-200 border border-rose-800/60'
                  : 'text-rose-400 hover:text-rose-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
              Errors ({errorCount})
            </button>
          )}
          {warningCount > 0 && (
            <button
              type="button"
              onClick={() => setFilterSeverity('WARNING')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
                filterSeverity === 'WARNING'
                  ? 'bg-amber-950/80 text-amber-200 border border-amber-800/60'
                  : 'text-amber-400 hover:text-amber-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Warnings ({warningCount})
            </button>
          )}
          {infoCount > 0 && (
            <button
              type="button"
              onClick={() => setFilterSeverity('INFO')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
                filterSeverity === 'INFO'
                  ? 'bg-blue-950/80 text-blue-200 border border-blue-800/60'
                  : 'text-blue-400 hover:text-blue-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
              Info ({infoCount})
            </button>
          )}
        </div>
      </div>

      {/* Findings cards */}
      <div className="space-y-3">
        {filteredFindings.map((finding) => (
          <div
            key={finding.id}
            className={`p-4 rounded-xl border transition-all ${getCardBorder(finding.severity)}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                {getSeverityIcon(finding.severity)}
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-100">
                      {finding.rule_id}
                    </span>
                    <Badge variant={finding.severity} size="sm">
                      {finding.severity}
                    </Badge>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/80">
                      field: {finding.field}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed font-normal">
                    {finding.message}
                  </p>
                </div>
              </div>
            </div>

            {/* Math Discrepancy Breakdown */}
            {(finding.actual_value !== null || finding.expected_value !== null || finding.difference !== null) && (
              <div className="mt-3 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
                {finding.actual_value !== null && (
                  <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] uppercase text-slate-400 block font-sans">
                      Actual Value
                    </span>
                    <span className="text-slate-100 font-semibold truncate block" title={finding.actual_value}>
                      {finding.actual_value}
                    </span>
                  </div>
                )}
                {finding.expected_value !== null && (
                  <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] uppercase text-slate-400 block font-sans">
                      Expected Value
                    </span>
                    <span className="text-emerald-400 font-semibold truncate block" title={finding.expected_value}>
                      {finding.expected_value}
                    </span>
                  </div>
                )}
                {finding.difference !== null && (
                  <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                    <span className="text-[10px] uppercase text-slate-400 block font-sans">
                      Mathematical Difference
                    </span>
                    <span
                      className={`font-semibold truncate block ${
                        Math.abs(Number(finding.difference)) > 0.05 ? 'text-rose-400' : 'text-slate-300'
                      }`}
                    >
                      {Number(finding.difference) > 0 ? `+${finding.difference}` : finding.difference}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Read-only Dismissal Status */}
            {finding.is_dismissed && (
              <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center gap-2 text-[11px] text-slate-400 italic">
                <User className="w-3 h-3 text-slate-500" />
                <span>
                  Finding dismissed by <strong className="text-slate-300 not-italic">{finding.dismissed_by || 'operator'}</strong>
                  {finding.dismissed_at && ` on ${formatDateTime(finding.dismissed_at)}`}
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
