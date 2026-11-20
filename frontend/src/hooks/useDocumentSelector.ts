import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/services/api'
import type { DocumentListItem } from '@/types/document'

export interface UseDocumentSelectorReturn {
  documents: DocumentListItem[]
  totalCount: number
  isLoading: boolean
  error: string | null
  search: string
  setSearch: (search: string) => void
  validationStatus: string
  setValidationStatus: (status: string) => void
  page: number
  setPage: (page: number) => void
  pageSize: number
  totalPages: number
  refresh: () => Promise<void>
}

export function useDocumentSelector(initialPageSize = 20): UseDocumentSelectorReturn {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState<string>('')
  const [validationStatus, setValidationStatus] = useState<string>('ALL')
  const [page, setPage] = useState<number>(1)
  const [pageSize] = useState<number>(initialPageSize)

  const activeRequestRef = useRef<number>(0)

  const fetchDocuments = useCallback(async () => {
    const requestId = ++activeRequestRef.current
    setIsLoading(true)
    setError(null)

    try {
      const params: {
        page: number
        page_size: number
        search?: string
        validation_status?: string
      } = {
        page,
        page_size: pageSize,
      }

      if (search.trim()) {
        params.search = search.trim()
      }

      if (validationStatus && validationStatus !== 'ALL') {
        params.validation_status = validationStatus
      }

      const res = await api.getDocuments(params)

      if (requestId === activeRequestRef.current) {
        setDocuments(res.results || [])
        setTotalCount(res.count || 0)
      }
    } catch (err: unknown) {
      if (requestId === activeRequestRef.current) {
        const msg = err instanceof Error ? err.message : 'Failed to retrieve document listing'
        setError(msg)
        setDocuments([])
        setTotalCount(0)
      }
    } finally {
      if (requestId === activeRequestRef.current) {
        setIsLoading(false)
      }
    }
  }, [page, pageSize, search, validationStatus])

  // Debounce search changes to avoid spamming the backend API
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDocuments()
    }, 250)

    return () => clearTimeout(timer)
  }, [fetchDocuments])

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  const handleSetSearch = useCallback((newSearch: string) => {
    setSearch(newSearch)
    setPage(1) // Reset to page 1 on new search
  }, [])

  const handleSetValidationStatus = useCallback((newStatus: string) => {
    setValidationStatus(newStatus)
    setPage(1) // Reset to page 1 on filter change
  }, [])

  return {
    documents,
    totalCount,
    isLoading,
    error,
    search,
    setSearch: handleSetSearch,
    validationStatus,
    setValidationStatus: handleSetValidationStatus,
    page,
    setPage,
    pageSize,
    totalPages,
    refresh: fetchDocuments,
  }
}
