import React from 'react'
import { Clock, Edit2, History, Info, ShieldCheck, User } from 'lucide-react'
import { formatBytes, formatDateTime } from '@/utils/formatters'
import type { AuditLog, DocumentDetail, ManualCorrectionsMetadata } from '@/types/document'

export interface AuditHistoryCardProps {
  document: DocumentDetail
  className?: string
}

export const AuditHistoryCard: React.FC<AuditHistoryCardProps> = ({
  document,
  className = '',
}) => {
  const auditLogs: AuditLog[] = document.audit_logs || []
  const metadata = (document.metadata || {}) as Record<string, unknown>
  const manualCorrections = (metadata.manual_corrections || null) as ManualCorrectionsMetadata | null

  return (
    <div className={`space-y-5 ${className}`}>
      {/* Correction Status Summary Banner */}
      {manualCorrections && manualCorrections.is_corrected && (
        <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/60 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-300 font-semibold text-xs">
              <Edit2 className="w-4 h-4 text-amber-400" />
              <span>Document Has Verified Human Corrections</span>
            </div>
            {manualCorrections.last_corrected_at && (
              <span className="text-[10px] text-amber-400/80 font-mono">
                {formatDateTime(manualCorrections.last_corrected_at)}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            This document was modified from its initial machine extraction. Original machine values are preserved in system metadata for full compliance and model evaluation traceability.
          </p>
          {manualCorrections.corrected_fields && manualCorrections.corrected_fields.length > 0 && (
            <div className="pt-1 flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-slate-400 font-medium">Modified Fields:</span>
              {manualCorrections.corrected_fields.map((fld) => (
                <span
                  key={fld}
                  className="px-2 py-0.5 rounded font-mono text-[10px] bg-amber-900/40 text-amber-200 border border-amber-700/60"
                >
                  {fld}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Audit Log Trail */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
          <History className="w-4 h-4 text-slate-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Immutable Audit Trail ({auditLogs.length})
          </h4>
        </div>

        {auditLogs.length === 0 ? (
          <div className="p-6 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800 space-y-1.5">
            <ShieldCheck className="w-6 h-6 text-slate-600 mx-auto" />
            <p className="text-xs text-slate-300 font-medium">No Audit Log Entries</p>
            <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
              This document has not undergone manual modifications, status overrides, or operator dismissals.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {auditLogs.map((log) => {
              const isCorrection = log.action === 'MANUAL_CORRECTION'

              return (
                <div
                  key={log.id}
                  className={`p-3.5 rounded-xl border space-y-2 text-xs transition-colors ${isCorrection
                      ? 'bg-slate-900/90 border-amber-800/50 shadow-sm'
                      : 'bg-slate-900/70 border-slate-800'
                    }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold border ${isCorrection
                            ? 'bg-amber-950/80 text-amber-300 border-amber-700/80'
                            : 'bg-slate-800 text-slate-200 border-slate-700'
                          }`}
                      >
                        {log.action}
                      </span>
                      {log.field_name && (
                        <span className="font-mono text-slate-400 text-[11px]">
                          field:{' '}
                          <strong className="text-brand-300 font-bold bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700">
                            {log.field_name}
                          </strong>
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 text-[11px] text-slate-400">
                      <Clock className="w-3 h-3 text-slate-500" />
                      <span>{formatDateTime(log.created_at)}</span>
                    </div>
                  </div>

                  {/* Old vs New values diff */}
                  {(log.old_value !== null || log.new_value !== null) && (
                    <div className="p-2.5 rounded bg-slate-950/90 border border-slate-800/80 font-mono text-[11px] space-y-1.5">
                      {log.old_value !== null && (
                        <div className="flex items-start gap-2 text-rose-300/80">
                          <span className="text-rose-400 font-bold select-none">-</span>
                          <span className="line-through break-all">{log.old_value || '""'}</span>
                        </div>
                      )}
                      {log.new_value !== null && (
                        <div className="flex items-start gap-2 text-emerald-300">
                          <span className="text-emerald-400 font-bold select-none">+</span>
                          <span className="break-all font-semibold">{log.new_value || '""'}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Reason and user */}
                  <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
                    <div className="flex items-center gap-1">
                      <User className="w-3 h-3 text-slate-500" />
                      <span>Operator: <strong className="text-slate-300">{log.user_id || 'system'}</strong></span>
                    </div>
                    {log.reason && (
                      <span className="italic text-slate-400 truncate max-w-xs" title={log.reason}>
                        "{log.reason}"
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Document Ingestion & Storage Metadata */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3 text-xs">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
          <Info className="w-4 h-4 text-slate-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Ingestion & Storage Metadata
          </h4>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 font-mono text-[11px]">
          <div className="p-2 rounded bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] uppercase text-slate-400 font-sans block">File Format</span>
            <span className="text-slate-200 uppercase font-semibold">{document.file_type}</span>
          </div>

          <div className="p-2 rounded bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] uppercase text-slate-400 font-sans block">File Size</span>
            <span className="text-slate-200 font-semibold">{formatBytes(document.file_size_bytes)}</span>
          </div>

          <div className="p-2 rounded bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] uppercase text-slate-400 font-sans block">Page Count</span>
            <span className="text-slate-200 font-semibold">{document.page_count} pages</span>
          </div>

          <div className="p-2 rounded bg-slate-950/60 border border-slate-800">
            <span className="text-[10px] uppercase text-slate-400 font-sans block">Ingested At</span>
            <span className="text-slate-300 font-sans">{formatDateTime(document.created_at)}</span>
          </div>

          <div className="p-2 rounded bg-slate-950/60 border border-slate-800 col-span-2 sm:col-span-2">
            <span className="text-[10px] uppercase text-slate-400 font-sans block">Internal Document UUID</span>
            <span className="text-slate-400 truncate block text-[10px]" title={document.id}>
              {document.id}
            </span>
          </div>
        </div>

        {/* Ingestion Pipeline Engine Metadata if present */}
        {Object.keys(metadata).length > 0 && (
          <div className="pt-2 border-t border-slate-800/80">
            <span className="text-[10px] uppercase text-slate-400 block pb-1.5 font-semibold">
              Extraction Pipeline Attributes
            </span>
            <pre className="p-2.5 rounded bg-slate-950/90 border border-slate-800 text-[10px] text-slate-400 overflow-x-auto max-h-32">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
