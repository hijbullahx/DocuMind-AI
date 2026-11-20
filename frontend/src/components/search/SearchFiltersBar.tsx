import React from 'react'
import { Filter, RotateCcw } from 'lucide-react'
import type { SearchFilters } from '@/hooks/useDocumentSearch'

export interface SearchFiltersBarProps {
  filters: SearchFilters
  onChangeFilters: (newFilters: Partial<SearchFilters>) => void
  onResetFilters: () => void
  className?: string
}

export const SearchFiltersBar: React.FC<SearchFiltersBarProps> = ({
  filters,
  onChangeFilters,
  onResetFilters,
  className = '',
}) => {
  const activeCount = Object.values(filters).filter(Boolean).length

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800/80 text-xs ${className}`}>
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="flex items-center gap-1.5 text-slate-400 font-medium">
          <Filter className="w-3.5 h-3.5 text-brand-400" />
          <span>Filters:</span>
        </span>

        {/* Status Dropdown */}
        <select
          value={filters.status || ''}
          onChange={(e) => onChangeFilters({ status: e.target.value || undefined })}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-brand-500"
        >
          <option value="">Status: All</option>
          <option value="SUCCESS">Success</option>
          <option value="PROCESSING">Processing</option>
          <option value="FAILED">Failed</option>
          <option value="PARTIAL_SUCCESS">Partial Success</option>
        </select>

        {/* Validation Status Dropdown */}
        <select
          value={filters.validation_status || ''}
          onChange={(e) => onChangeFilters({ validation_status: e.target.value || undefined })}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-brand-500"
        >
          <option value="">Validation: All</option>
          <option value="VERIFIED">Verified</option>
          <option value="NEEDS_REVIEW">Needs Review</option>
          <option value="FAILED">Failed</option>
          <option value="PENDING">Pending</option>
        </select>

        {/* File Type Dropdown */}
        <select
          value={filters.file_type || ''}
          onChange={(e) => onChangeFilters({ file_type: e.target.value || undefined })}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-brand-500"
        >
          <option value="">Type: All</option>
          <option value="pdf">PDF</option>
          <option value="png">PNG</option>
          <option value="jpg">JPG / JPEG</option>
          <option value="xlsx">Excel (XLSX)</option>
          <option value="csv">CSV</option>
        </select>

        {/* Date From */}
        <div className="flex items-center gap-1 text-slate-400">
          <span className="text-[11px]">From:</span>
          <input
            type="date"
            value={filters.date_from || ''}
            onChange={(e) => onChangeFilters({ date_from: e.target.value || undefined })}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-slate-300 text-[11px] focus:outline-none focus:border-brand-500"
          />
        </div>

        {/* Date To */}
        <div className="flex items-center gap-1 text-slate-400">
          <span className="text-[11px]">To:</span>
          <input
            type="date"
            value={filters.date_to || ''}
            onChange={(e) => onChangeFilters({ date_to: e.target.value || undefined })}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-slate-300 text-[11px] focus:outline-none focus:border-brand-500"
          />
        </div>
      </div>

      {/* Clear/Reset action */}
      {activeCount > 0 && (
        <button
          type="button"
          onClick={onResetFilters}
          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors font-medium text-xs"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset ({activeCount})</span>
        </button>
      )}
    </div>
  )
}
