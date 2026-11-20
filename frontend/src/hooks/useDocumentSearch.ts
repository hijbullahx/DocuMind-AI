import { useCallback, useRef, useState } from 'react'
import { api, ApiError } from '@/services/api'
import type { SearchQueryParams, SearchResultItem } from '@/types/search'

export interface SearchFilters {
  status?: string
  validation_status?: string
  file_type?: string
  date_from?: string
  date_to?: string
  supplier?: string
  customer?: string
}

export function useDocumentSearch(initialQuery = '', initialFilters: SearchFilters = {}) {
  const [query, setQuery] = useState(initialQuery)
  const [filters, setFilters] = useState<SearchFilters>(initialFilters)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const [results, setResults] = useState<SearchResultItem[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)

  // Stale request protection
  const activeRequestId = useRef(0)

  const executeSearch = useCallback(
    async (
      overrideQuery?: string,
      overridePage?: number,
      overrideFilters?: SearchFilters
    ) => {
      const q = overrideQuery !== undefined ? overrideQuery : query
      const p = overridePage !== undefined ? overridePage : page
      const f = overrideFilters !== undefined ? overrideFilters : filters

      const trimmed = q.trim()
      const hasActiveFilters = Boolean(
        f.status ||
          f.validation_status ||
          f.file_type ||
          f.date_from ||
          f.date_to ||
          f.supplier ||
          f.customer
      )

      // If both query and filters are empty, reset to initial state
      if (!trimmed && !hasActiveFilters) {
        setResults([])
        setTotalCount(0)
        setTotalPages(0)
        setError(null)
        setHasSearched(false)
        return
      }

      const reqId = ++activeRequestId.current
      setIsLoading(true)
      setError(null)
      setHasSearched(true)

      try {
        const params: SearchQueryParams = {
          q: trimmed,
          page: p,
          page_size: pageSize,
          status: f.status || undefined,
          validation_status: f.validation_status || undefined,
          file_type: f.file_type || undefined,
          date_from: f.date_from || undefined,
          date_to: f.date_to || undefined,
          supplier: f.supplier || undefined,
          customer: f.customer || undefined,
        }

        const data = await api.searchDocuments(params)

        if (reqId === activeRequestId.current) {
          setResults(data.results || [])
          setTotalCount(data.count || 0)
          setTotalPages(data.total_pages || 0)
        }
      } catch (err) {
        if (reqId === activeRequestId.current) {
          const msg =
            err instanceof ApiError
              ? err.message
              : err instanceof Error
              ? err.message
              : 'Search request failed'
          setError(msg)
          setResults([])
          setTotalCount(0)
          setTotalPages(0)
        }
      } finally {
        if (reqId === activeRequestId.current) {
          setIsLoading(false)
        }
      }
    },
    [query, page, pageSize, filters]
  )

  const updateFilters = useCallback(
    (newFilters: Partial<SearchFilters>) => {
      const updated = { ...filters, ...newFilters }
      // Remove empty keys
      Object.keys(updated).forEach((k) => {
        const key = k as keyof SearchFilters
        if (!updated[key]) delete updated[key]
      })
      setFilters(updated)
      setPage(1)
      executeSearch(query, 1, updated)
    },
    [filters, query, executeSearch]
  )

  const resetFilters = useCallback(() => {
    setFilters({})
    setPage(1)
    executeSearch(query, 1, {})
  }, [query, executeSearch])

  const clearSearch = useCallback(() => {
    setQuery('')
    setFilters({})
    setPage(1)
    setResults([])
    setTotalCount(0)
    setTotalPages(0)
    setError(null)
    setHasSearched(false)
  }, [])

  const handlePageChange = useCallback(
    (newPage: number) => {
      setPage(newPage)
      executeSearch(query, newPage, filters)
    },
    [query, filters, executeSearch]
  )

  return {
    query,
    setQuery,
    filters,
    updateFilters,
    resetFilters,
    page,
    setPage: handlePageChange,
    pageSize,
    setPageSize,
    results,
    totalCount,
    totalPages,
    isLoading,
    error,
    hasSearched,
    executeSearch,
    clearSearch,
  }
}
