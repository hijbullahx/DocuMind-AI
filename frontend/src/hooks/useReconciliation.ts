import { useCallback, useEffect, useState } from 'react'
import { api } from '@/services/api'
import type { DocumentListItem } from '@/types/document'
import type { ReconciliationRecord } from '@/types/reconciliation'

export interface UseReconciliationReturn {
  // Document selection
  selectedDocA: DocumentListItem | null
  selectedDocB: DocumentListItem | null
  setSelectedDocA: (doc: DocumentListItem | null) => void
  setSelectedDocB: (doc: DocumentListItem | null) => void
  swapDocuments: () => void
  resetSelection: () => void

  // Configuration
  tolerance: number
  setTolerance: (tol: number) => void
  strictReferenceMatching: boolean
  setStrictReferenceMatching: (val: boolean) => void

  // Execution & State
  currentResult: ReconciliationRecord | null
  isReconciling: boolean
  reconciliationError: string | null
  executeReconciliation: () => Promise<boolean>
  reReconcileCurrent: () => Promise<boolean>
  loadReconciliationById: (id: string) => Promise<void>
  clearResult: () => void

  // History
  history: ReconciliationRecord[]
  isLoadingHistory: boolean
  refreshHistory: () => Promise<void>
}

export function useReconciliation(initialReconciliationId?: string | null): UseReconciliationReturn {
  const [selectedDocA, setSelectedDocA] = useState<DocumentListItem | null>(null)
  const [selectedDocB, setSelectedDocB] = useState<DocumentListItem | null>(null)
  const [tolerance, setTolerance] = useState<number>(0.05)
  const [strictReferenceMatching, setStrictReferenceMatching] = useState<boolean>(false)

  const [currentResult, setCurrentResult] = useState<ReconciliationRecord | null>(null)
  const [isReconciling, setIsReconciling] = useState<boolean>(false)
  const [reconciliationError, setReconciliationError] = useState<string | null>(null)

  const [history, setHistory] = useState<ReconciliationRecord[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false)

  const refreshHistory = useCallback(async () => {
    setIsLoadingHistory(true)
    try {
      const res = await api.getReconciliations({ page_size: 20 })
      setHistory(res.results || [])
    } catch {
      setHistory([])
    } finally {
      setIsLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    refreshHistory()
  }, [refreshHistory])

  const loadReconciliationById = useCallback(async (id: string) => {
    setIsReconciling(true)
    setReconciliationError(null)
    try {
      const record = await api.getReconciliationDetail(id)
      setCurrentResult(record)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load reconciliation record'
      setReconciliationError(msg)
    } finally {
      setIsReconciling(false)
    }
  }, [])

  useEffect(() => {
    if (initialReconciliationId) {
      loadReconciliationById(initialReconciliationId)
    }
  }, [initialReconciliationId, loadReconciliationById])

  const executeReconciliation = useCallback(async (): Promise<boolean> => {
    if (!selectedDocA || !selectedDocB) {
      setReconciliationError('Please select two distinct documents to reconcile.')
      return false
    }

    if (selectedDocA.id === selectedDocB.id) {
      setReconciliationError('Self-reconciliation is not permitted. Please select two distinct documents.')
      return false
    }

    setIsReconciling(true)
    setReconciliationError(null)

    try {
      const record = await api.runReconciliation({
        doc_a_id: selectedDocA.id,
        doc_b_id: selectedDocB.id,
        tolerance,
        strict_reference_matching: strictReferenceMatching,
      })
      setCurrentResult(record)
      await refreshHistory()
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reconciliation execution failed'
      setReconciliationError(msg)
      return false
    } finally {
      setIsReconciling(false)
    }
  }, [selectedDocA, selectedDocB, tolerance, strictReferenceMatching, refreshHistory])

  const reReconcileCurrent = useCallback(async (): Promise<boolean> => {
    if (!currentResult) return false

    setIsReconciling(true)
    setReconciliationError(null)

    try {
      const newRecord = await api.reReconcile(currentResult.id, tolerance)
      setCurrentResult(newRecord)
      await refreshHistory()
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Re-reconciliation failed'
      setReconciliationError(msg)
      return false
    } finally {
      setIsReconciling(false)
    }
  }, [currentResult, tolerance, refreshHistory])

  const swapDocuments = useCallback(() => {
    setSelectedDocA(selectedDocB)
    setSelectedDocB(selectedDocA)
  }, [selectedDocA, selectedDocB])

  const resetSelection = useCallback(() => {
    setSelectedDocA(null)
    setSelectedDocB(null)
    setCurrentResult(null)
    setReconciliationError(null)
  }, [])

  const clearResult = useCallback(() => {
    setCurrentResult(null)
    setReconciliationError(null)
  }, [])

  return {
    selectedDocA,
    selectedDocB,
    setSelectedDocA,
    setSelectedDocB,
    swapDocuments,
    resetSelection,
    tolerance,
    setTolerance,
    strictReferenceMatching,
    setStrictReferenceMatching,
    currentResult,
    isReconciling,
    reconciliationError,
    executeReconciliation,
    reReconcileCurrent,
    loadReconciliationById,
    clearResult,
    history,
    isLoadingHistory,
    refreshHistory,
  }
}
