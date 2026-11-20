import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/services/api'
import type { DocumentDetail } from '@/types/document'

export type ReviewTab = 'fields' | 'items' | 'validations' | 'audit'

export interface UseDocumentReviewReturn {
  document: DocumentDetail | null
  isLoading: boolean
  error: string | null
  isReprocessing: boolean
  reprocessMessage: string | null
  reprocessError: string | null

  // Evidence grounding state
  activeEvidenceKey: string | null
  activeEvidenceQuote: string | null
  setEvidenceHighlight: (key: string, quote: string | null) => void
  clearEvidenceHighlight: () => void

  // Search state for raw text viewer
  searchQuery: string
  setSearchQuery: (query: string) => void

  // Active tab state
  activeTab: ReviewTab
  setActiveTab: (tab: ReviewTab) => void

  // Operations
  refresh: () => Promise<void>
  reprocess: (force?: boolean) => Promise<boolean>
}

export function useDocumentReview(documentId: string | null): UseDocumentReviewReturn {
  const [document, setDocument] = useState<DocumentDetail | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const [isReprocessing, setIsReprocessing] = useState<boolean>(false)
  const [reprocessMessage, setReprocessMessage] = useState<string | null>(null)
  const [reprocessError, setReprocessError] = useState<string | null>(null)

  const [activeEvidenceKey, setActiveEvidenceKey] = useState<string | null>(null)
  const [activeEvidenceQuote, setActiveEvidenceQuote] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [activeTab, setActiveTab] = useState<ReviewTab>('fields')

  // Keep track of active fetch to prevent stale state updates
  const activeFetchIdRef = useRef<string | null>(null)

  const fetchDetail = useCallback(async (id: string) => {
    activeFetchIdRef.current = id
    setIsLoading(true)
    setError(null)
    setReprocessMessage(null)
    setReprocessError(null)

    try {
      const data = await api.getDocumentDetail(id)
      if (activeFetchIdRef.current === id) {
        setDocument(data)
      }
    } catch (err: unknown) {
      if (activeFetchIdRef.current === id) {
        const msg = err instanceof Error ? err.message : 'Failed to retrieve document details'
        setError(msg)
        setDocument(null)
      }
    } finally {
      if (activeFetchIdRef.current === id) {
        setIsLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    setActiveEvidenceKey(null)
    setActiveEvidenceQuote(null)
    setSearchQuery('')
    setActiveTab('fields')

    if (documentId) {
      fetchDetail(documentId)
    } else {
      setDocument(null)
      setIsLoading(false)
      setError(null)
    }
  }, [documentId, fetchDetail])

  const refresh = useCallback(async () => {
    if (documentId) {
      await fetchDetail(documentId)
    }
  }, [documentId, fetchDetail])

  const reprocess = useCallback(
    async (force = false): Promise<boolean> => {
      if (!documentId || isReprocessing) return false

      setIsReprocessing(true)
      setReprocessError(null)
      setReprocessMessage(null)

      try {
        const res = await api.reprocessDocument(documentId, force)
        setReprocessMessage(res.message || 'Reprocessing job enqueued successfully.')
        // Refresh document details to reflect newly queued status
        await fetchDetail(documentId)
        return true
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to reprocess document'
        setReprocessError(msg)
        return false
      } finally {
        setIsReprocessing(false)
      }
    },
    [documentId, isReprocessing, fetchDetail]
  )

  const setEvidenceHighlight = useCallback((key: string, quote: string | null) => {
    if (!quote || quote.trim() === '') {
      setActiveEvidenceKey(null)
      setActiveEvidenceQuote(null)
      return
    }

    setActiveEvidenceKey((prevKey) => {
      // Toggle off if clicking the already active key
      if (prevKey === key) {
        setActiveEvidenceQuote(null)
        return null
      }
      setActiveEvidenceQuote(quote.trim())
      return key
    })
  }, [])

  const clearEvidenceHighlight = useCallback(() => {
    setActiveEvidenceKey(null)
    setActiveEvidenceQuote(null)
  }, [])

  return {
    document,
    isLoading,
    error,
    isReprocessing,
    reprocessMessage,
    reprocessError,
    activeEvidenceKey,
    activeEvidenceQuote,
    setEvidenceHighlight,
    clearEvidenceHighlight,
    searchQuery,
    setSearchQuery,
    activeTab,
    setActiveTab,
    refresh,
    reprocess,
  }
}
