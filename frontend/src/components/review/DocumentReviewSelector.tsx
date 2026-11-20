import React from 'react'
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { formatBytes, formatDate } from '@/utils/formatters'
import type { DocumentListItem } from '@/types/document'

export interface DocumentReviewSelectorProps {
  documents: DocumentListItem[]
  totalCount: number
  selectedId: string | null
  onSelectDocument: (id: string) => void
  isLoading: boolean
  error: string | null
  search: string
  onSearchChange: (search: string) => void
  validationStatus: string
  onValidationStatusChange: (status: string) => void
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  onRefresh: () => void
  onClose: () => void
  className?: string
}

export const DocumentReviewSelector: React.FC<DocumentReviewSelectorProps> = ({
  documents,
  totalCount,
  selectedId,
  onSelectDocument,
  isLoading,
  error,
  search,
  onSearchChange,
  validationStatus,
  onValidationStatusChange,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  onClose,
  className = '',
}) => {
  const statusOptions = [
    { label: 'All', value: 'ALL' },
    { label: 'Needs Review', value: 'NEEDS_REVIEW' },
    { label: 'Verified', value: 'VERIFIED' },
    { label: 'Failed', value: 'FAILED' },
    { label: 'Pending', value: 'PENDING' },
  ]

  return (
    <div
      className={`flex flex-col h-full bg-slate-900 border-r border-slate-800 w-80 sm:w-88 shrink-0 z-20 ${className}`}
    >
      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between gap-2 shrink-0 bg-slate-950/60">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Select Document ({totalCount})
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onRefresh}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Refresh document list"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close document selector"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="p-3 border-b border-slate-800 space-y-2 shrink-0 bg-slate-950/40">
        {/* Search input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search by filename or ID..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-8 pr-7 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Validation Status Filter Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px]">
          {statusOptions.map((opt) => {
            const isSelected = validationStatus === opt.value
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onValidationStatusChange(opt.value)}
                className={`px-2 py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  isSelected
                    ? 'bg-brand-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {isLoading && documents.length === 0 ? (
          <div className="p-8 text-center text-slate-400 space-y-2">
            <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-400" />
            <p className="text-xs">Loading documents...</p>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-rose-400 space-y-2">
            <AlertCircle className="w-5 h-5 mx-auto" />
            <p className="text-xs">{error}</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center text-slate-500 space-y-1">
            <p className="text-xs font-medium text-slate-400">No documents found</p>
            <p className="text-[11px]">Try adjusting your search or status filter.</p>
          </div>
        ) : (
          documents.map((doc) => {
            const isSelected = doc.id === selectedId
            return (
              <button
                key={doc.id}
                type="button"
                onClick={() => onSelectDocument(doc.id)}
                className={`w-full text-left p-3 rounded-xl border transition-all space-y-1.5 ${
                  isSelected
                    ? 'bg-blue-950/60 border-blue-600 text-white shadow-sm'
                    : 'bg-slate-900/60 hover:bg-slate-800/60 border-slate-800/80 text-slate-300'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-xs truncate leading-snug" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <Badge variant={doc.validation_status} size="sm">
                    {doc.validation_status}
                  </Badge>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span className="uppercase">{doc.file_type} • {formatBytes(doc.file_size_bytes)}</span>
                  <span>{formatDate(doc.created_at)}</span>
                </div>
              </button>
            )
          })
        )}
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="p-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 shrink-0 bg-slate-950/60">
          <span>
            Page <strong className="text-slate-200">{page}</strong> of <strong className="text-slate-200">{totalPages}</strong>
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
