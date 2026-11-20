import React, { useEffect, useState } from 'react'
import {
  ArrowLeftRight,
  GitCompare,
  Search,
  Sparkles,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api } from '@/services/api'
import { formatBytes } from '@/utils/formatters'
import type { DocumentListItem } from '@/types/document'

export interface DualDocumentSelectorProps {
  selectedDocA: DocumentListItem | null
  selectedDocB: DocumentListItem | null
  onSelectDocA: (doc: DocumentListItem | null) => void
  onSelectDocB: (doc: DocumentListItem | null) => void
  onSwapDocuments: () => void
  onReset: () => void
  tolerance: number
  onChangeTolerance: (tol: number) => void
  isReconciling: boolean
  onRunReconciliation: () => void
  className?: string
}

export const DualDocumentSelector: React.FC<DualDocumentSelectorProps> = ({
  selectedDocA,
  selectedDocB,
  onSelectDocA,
  onSelectDocB,
  onSwapDocuments,
  onReset,
  tolerance,
  onChangeTolerance,
  isReconciling,
  onRunReconciliation,
  className = '',
}) => {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(false)
  const [searchA, setSearchA] = useState<string>('')
  const [searchB, setSearchB] = useState<string>('')

  // Fetch documents that have completed extraction
  useEffect(() => {
    let isMounted = true
    const loadEligibleDocs = async () => {
      setIsLoadingDocs(true)
      try {
        const res = await api.getDocuments({ page_size: 50 })
        if (isMounted) {
          // Filter to ready/verified/reviewed docs that have completed processing
          const eligible = (res.results || []).filter(
            (d) => d.status === 'SUCCESS' || d.status === 'PARTIAL_SUCCESS' || d.status === 'FAILED'
          )
          setDocuments(eligible)
        }
      } catch {
        if (isMounted) setDocuments([])
      } finally {
        if (isMounted) setIsLoadingDocs(false)
      }
    }
    loadEligibleDocs()
    return () => {
      isMounted = false
    }
  }, [])

  const filteredDocsA = documents.filter((d) => {
    if (!searchA.trim()) return true
    return (
      d.filename.toLowerCase().includes(searchA.toLowerCase()) ||
      d.file_type.toLowerCase().includes(searchA.toLowerCase())
    )
  })

  const filteredDocsB = documents.filter((d) => {
    if (!searchB.trim()) return true
    return (
      d.filename.toLowerCase().includes(searchB.toLowerCase()) ||
      d.file_type.toLowerCase().includes(searchB.toLowerCase())
    )
  })

  const canReconcile =
    selectedDocA !== null &&
    selectedDocB !== null &&
    selectedDocA.id !== selectedDocB.id &&
    !isReconciling

  const renderDocCard = (
    label: string,
    doc: DocumentListItem | null,
    search: string,
    setSearch: (v: string) => void,
    filteredList: DocumentListItem[],
    onSelect: (d: DocumentListItem | null) => void,
    otherSelectedId: string | undefined,
    colorTheme: 'blue' | 'emerald'
  ) => {
    const borderColor = colorTheme === 'blue' ? 'border-blue-500/40' : 'border-emerald-500/40'
    const badgeColor = colorTheme === 'blue' ? 'bg-blue-950/80 text-blue-300' : 'bg-emerald-950/80 text-emerald-300'

    return (
      <div className={`p-4 rounded-xl border bg-slate-900/80 space-y-3 flex-1 min-w-[280px] ${borderColor}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-[11px] font-bold font-mono uppercase ${badgeColor}`}>
              {label}
            </span>
            <span className="text-xs text-slate-300 font-medium">
              {doc ? doc.filename : 'No document selected'}
            </span>
          </div>
          {doc && (
            <button
              type="button"
              onClick={() => onSelect(null)}
              className="text-[11px] text-slate-400 hover:text-rose-400 transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Selected Doc Summary Card */}
        {doc ? (
          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5 text-xs font-mono">
            <div className="flex items-center justify-between">
              <span className="text-slate-200 font-semibold truncate max-w-[200px]" title={doc.filename}>
                {doc.filename}
              </span>
              <Badge variant={doc.status} size="sm">
                {doc.status}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <span className="uppercase">{doc.file_type}</span>
              <span>•</span>
              <span>{formatBytes(doc.file_size_bytes)}</span>
              <span>•</span>
              <span className="capitalize">{doc.validation_status}</span>
            </div>
          </div>
        ) : (
          /* Selection Dropdown / Search */
          <div className="space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search extracted documents..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="max-h-40 overflow-y-auto space-y-1 rounded-lg border border-slate-800/80 p-1 bg-slate-950/60">
              {isLoadingDocs ? (
                <div className="text-center py-3 text-xs text-slate-500">Loading documents...</div>
              ) : filteredList.length === 0 ? (
                <div className="text-center py-3 text-xs text-slate-500">No matching documents</div>
              ) : (
                filteredList.map((d) => {
                  const isOther = d.id === otherSelectedId
                  return (
                    <button
                      key={d.id}
                      type="button"
                      disabled={isOther}
                      onClick={() => onSelect(d)}
                      className={`w-full text-left p-2 rounded flex items-center justify-between text-xs transition-colors ${
                        isOther
                          ? 'opacity-40 cursor-not-allowed bg-slate-900/20 text-slate-500'
                          : 'hover:bg-slate-800 text-slate-300 hover:text-white'
                      }`}
                    >
                      <div className="truncate pr-2">
                        <div className="font-medium truncate">{d.filename}</div>
                        <div className="text-[10px] text-slate-500 uppercase">{d.file_type} • {d.validation_status}</div>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono shrink-0">Select</span>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={`p-4 sm:p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4 shadow-sm ${className}`}>
      {/* Top Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
            <GitCompare className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-semibold text-slate-100">
              Cross-Document Reconciliation Pair
            </h3>
            <p className="text-xs text-slate-400">
              Select two extracted documents (Invoices, Purchase Orders, or Excel Ledgers) to audit discrepancies.
            </p>
          </div>
        </div>

        {/* Tolerance and Reset Actions */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <span>Tolerance:</span>
            <select
              value={tolerance}
              onChange={(e) => onChangeTolerance(Number(e.target.value))}
              className="bg-transparent text-slate-200 font-mono font-semibold focus:outline-none"
            >
              <option value={0.01} className="bg-slate-900 text-slate-200">$0.01 (Strict)</option>
              <option value={0.05} className="bg-slate-900 text-slate-200">$0.05 (Standard)</option>
              <option value={0.10} className="bg-slate-900 text-slate-200">$0.10</option>
              <option value={1.00} className="bg-slate-900 text-slate-200">$1.00</option>
            </select>
          </div>

          {(selectedDocA || selectedDocB) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReset}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Reset
            </Button>
          )}
        </div>
      </div>

      {/* Dual Document Selector Panels */}
      <div className="flex flex-col md:flex-row items-center gap-3">
        {/* Document A */}
        {renderDocCard(
          'Document A (Primary)',
          selectedDocA,
          searchA,
          setSearchA,
          filteredDocsA,
          onSelectDocA,
          selectedDocB?.id,
          'blue'
        )}

        {/* Swap Button */}
        <button
          type="button"
          onClick={onSwapDocuments}
          disabled={!selectedDocA && !selectedDocB}
          className="p-2.5 rounded-full bg-slate-950 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
          title="Swap Document A and Document B"
        >
          <ArrowLeftRight className="w-4 h-4" />
        </button>

        {/* Document B */}
        {renderDocCard(
          'Document B (Comparison)',
          selectedDocB,
          searchB,
          setSearchB,
          filteredDocsB,
          onSelectDocB,
          selectedDocA?.id,
          'emerald'
        )}
      </div>

      {/* Execute Reconciliation Action Bar */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
        <span className="text-xs text-slate-400">
          {canReconcile
            ? 'Ready to reconcile. Comparing financial entities, invoice references, and line item pairings.'
            : 'Select two distinct processed documents to enable cross-reconciliation.'}
        </span>

        <Button
          variant="primary"
          size="sm"
          disabled={!canReconcile}
          isLoading={isReconciling}
          onClick={onRunReconciliation}
          leftIcon={<Sparkles className="w-4 h-4" />}
          className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs px-4 py-2"
        >
          Reconcile Documents
        </Button>
      </div>
    </div>
  )
}
