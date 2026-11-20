import React from 'react'
import {
  Search,
  FileText,
  Building2,
  FileSpreadsheet,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Layers,
  Sparkles,
} from 'lucide-react'
import { useDocumentSearch } from '@/hooks/useDocumentSearch'
import { SearchBar } from '@/components/search/SearchBar'
import { SearchFiltersBar } from '@/components/search/SearchFiltersBar'
import { SearchResultCard } from '@/components/search/SearchResultCard'

export interface SearchViewProps {
  onNavigateToReview: (documentId: string) => void
  className?: string
}

export const SearchView: React.FC<SearchViewProps> = ({
  onNavigateToReview,
  className = '',
}) => {
  const {
    query,
    setQuery,
    filters,
    updateFilters,
    resetFilters,
    page,
    setPage,
    results,
    totalCount,
    totalPages,
    isLoading,
    error,
    hasSearched,
    executeSearch,
    clearSearch,
  } = useDocumentSearch()

  return (
    <div className={`space-y-6 max-w-5xl mx-auto pb-16 ${className}`}>
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-2xl shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
            <Search className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Full-Text Document & Extraction Search
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-brand-950/80 text-brand-300 border border-brand-800/50">
                TASK-019
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Ranked search across filenames, invoice numbers, suppliers, line items, and OCR text.
            </p>
          </div>
        </div>

        {hasSearched && (
          <div className="text-xs font-mono text-slate-400">
            <span>{totalCount} result{totalCount === 1 ? '' : 's'}</span>
          </div>
        )}
      </div>

      {/* Search Input Bar */}
      <SearchBar
        value={query}
        onChange={setQuery}
        onSearch={() => executeSearch(query, 1)}
        onClear={clearSearch}
        isLoading={isLoading}
      />

      {/* Search Filters Bar */}
      <SearchFiltersBar
        filters={filters}
        onChangeFilters={updateFilters}
        onResetFilters={resetFilters}
      />

      {/* Error Banner */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 flex items-center justify-between text-rose-300 text-xs">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Search error: {error}</span>
          </div>
          <button
            onClick={() => executeSearch(query, page)}
            className="text-xs font-semibold underline hover:text-white"
          >
            Retry
          </button>
        </div>
      )}

      {/* Results / Empty / Loading States */}
      {isLoading ? (
        /* Loading Skeleton */
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="p-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl animate-pulse space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="h-4 bg-slate-800 rounded w-48" />
                <div className="h-4 bg-slate-800 rounded w-20" />
              </div>
              <div className="h-3 bg-slate-800/60 rounded w-3/4" />
              <div className="h-10 bg-slate-950/60 rounded-xl" />
            </div>
          ))}
        </div>
      ) : hasSearched && results.length > 0 ? (
        /* Search Results List */
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span>
              Showing {results.length} of {totalCount} matching document{totalCount === 1 ? '' : 's'}
            </span>
            {totalPages > 1 && (
              <span>
                Page {page} of {totalPages}
              </span>
            )}
          </div>

          <div className="space-y-3">
            {results.map((item) => (
              <SearchResultCard
                key={item.id}
                item={item}
                onSelectDocument={onNavigateToReview}
              />
            ))}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Previous</span>
              </button>

              <span className="text-xs font-mono text-slate-400">
                Page {page} of {totalPages}
              </span>

              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <span>Next</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      ) : hasSearched && results.length === 0 ? (
        /* No Results State */
        <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl max-w-xl mx-auto space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-slate-800 text-slate-400 flex items-center justify-center mx-auto mb-2">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-100">No documents found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
            No documents matched your search query &ldquo;{query}&rdquo;. Try checking for typos, loosening applied filters, or searching by generic keywords.
          </p>
        </div>
      ) : (
        /* Initial Landing State before search */
        <div className="bg-slate-900 border border-dashed border-slate-800 rounded-2xl p-10 text-center max-w-2xl mx-auto space-y-6">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mx-auto text-brand-400">
            <Sparkles className="w-7 h-7" />
          </div>

          <div className="space-y-1.5">
            <h3 className="text-base font-bold text-white">Indexed Document Intelligence Search</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              Enter keywords, invoice numbers, vendor names, or product descriptions to query indexed documents.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
            <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800/80 space-y-1">
              <div className="text-xs font-semibold text-brand-300 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-brand-400" />
                <span>1. Invoice & Reference #</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Matches exact invoice numbers with boosted relevance ranking.
              </p>
            </div>

            <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800/80 space-y-1">
              <div className="text-xs font-semibold text-brand-300 flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-brand-400" />
                <span>2. Suppliers & Entities</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Identifies vendor names, billing addresses, and customer entities.
              </p>
            </div>

            <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800/80 space-y-1">
              <div className="text-xs font-semibold text-brand-300 flex items-center gap-1.5">
                <FileSpreadsheet className="w-3.5 h-3.5 text-brand-400" />
                <span>3. Line-Item Details</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Searches product names, SKU descriptions, and service particulars.
              </p>
            </div>

            <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800/80 space-y-1">
              <div className="text-xs font-semibold text-brand-300 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-brand-400" />
                <span>4. Raw OCR Text</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Full-text search across body text with safe highlighted excerpts.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
