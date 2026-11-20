import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '@/services/api'
import { calculateLineItemAmount, calculateLineItemsSum, safeRound } from '@/utils/calculator'
import type {
  DocumentCorrectionPayload,
  DocumentDetail,
  LineItemCorrectionPayload,
} from '@/types/document'

export type ReviewTab = 'fields' | 'items' | 'validations' | 'audit'

export interface EditableExtractionDraft {
  invoice_number: string
  invoice_date: string
  due_date: string
  supplier_name: string
  supplier_address: string
  customer_name: string
  customer_address: string
  subtotal: number | null
  tax: number | null
  total: number | null
  currency: string
  line_items: LineItemCorrectionPayload[]
  reason: string
}

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

  // Edit Mode & Correction State (TASK-017)
  isEditMode: boolean
  setIsEditMode: (mode: boolean) => void
  draft: EditableExtractionDraft
  isDirty: boolean
  dirtyFieldCount: number
  isSavingCorrection: boolean
  correctionError: string | null
  correctionSuccessMessage: string | null
  updateDraftField: (
    field: keyof Omit<EditableExtractionDraft, 'line_items'>,
    value: string | number | null
  ) => void
  updateDraftLineItem: (
    index: number,
    updatedItem: Partial<LineItemCorrectionPayload>
  ) => void
  addDraftLineItem: () => void
  removeDraftLineItem: (index: number) => void
  applyCalculatedSubtotal: () => void
  applyCalculatedTotal: () => void
  saveCorrections: (operator?: string) => Promise<boolean>
  cancelEditing: () => void
  resetDraft: () => void

  // Operations
  refresh: () => Promise<void>
  reprocess: (force?: boolean) => Promise<boolean>
}

const EMPTY_DRAFT: EditableExtractionDraft = {
  invoice_number: '',
  invoice_date: '',
  due_date: '',
  supplier_name: '',
  supplier_address: '',
  customer_name: '',
  customer_address: '',
  subtotal: null,
  tax: null,
  total: null,
  currency: 'USD',
  line_items: [],
  reason: '',
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

  // TASK-017: Edit & Correction state
  const [isEditMode, setIsEditMode] = useState<boolean>(false)
  const [draft, setDraft] = useState<EditableExtractionDraft>(EMPTY_DRAFT)
  const [isSavingCorrection, setIsSavingCorrection] = useState<boolean>(false)
  const [correctionError, setCorrectionError] = useState<string | null>(null)
  const [correctionSuccessMessage, setCorrectionSuccessMessage] = useState<string | null>(null)

  // Keep track of active fetch to prevent stale state updates
  const activeFetchIdRef = useRef<string | null>(null)

  // Initialize draft from document extraction
  const initializeDraftFromDoc = useCallback((doc: DocumentDetail | null) => {
    if (!doc || !doc.extraction) {
      setDraft(EMPTY_DRAFT)
      return
    }
    const ext = doc.extraction
    const items: LineItemCorrectionPayload[] = (ext.line_items || []).map((it) => ({
      id: it.id,
      line_number: it.line_number,
      description: it.description,
      quantity: it.quantity,
      unit_price: it.unit_price,
      amount: it.amount,
    }))

    setDraft({
      invoice_number: ext.invoice_number || '',
      invoice_date: ext.invoice_date || '',
      due_date: ext.due_date || '',
      supplier_name: ext.supplier_name || '',
      supplier_address: ext.supplier_address || '',
      customer_name: ext.customer_name || '',
      customer_address: ext.customer_address || '',
      subtotal: ext.subtotal !== null ? safeRound(ext.subtotal, 2) : null,
      tax: ext.tax !== null ? safeRound(ext.tax, 2) : null,
      total: ext.total !== null ? safeRound(ext.total, 2) : null,
      currency: ext.currency || 'USD',
      line_items: items,
      reason: '',
    })
  }, [])

  const fetchDetail = useCallback(
    async (id: string) => {
      activeFetchIdRef.current = id
      setIsLoading(true)
      setError(null)
      setReprocessMessage(null)
      setReprocessError(null)

      try {
        const data = await api.getDocumentDetail(id)
        if (activeFetchIdRef.current === id) {
          setDocument(data)
          initializeDraftFromDoc(data)
        }
      } catch (err: unknown) {
        if (activeFetchIdRef.current === id) {
          const msg = err instanceof Error ? err.message : 'Failed to retrieve document details'
          setError(msg)
          setDocument(null)
          setDraft(EMPTY_DRAFT)
        }
      } finally {
        if (activeFetchIdRef.current === id) {
          setIsLoading(false)
        }
      }
    },
    [initializeDraftFromDoc]
  )

  useEffect(() => {
    setActiveEvidenceKey(null)
    setActiveEvidenceQuote(null)
    setSearchQuery('')
    setActiveTab('fields')
    setIsEditMode(false)
    setCorrectionError(null)
    setCorrectionSuccessMessage(null)

    if (documentId) {
      fetchDetail(documentId)
    } else {
      setDocument(null)
      setDraft(EMPTY_DRAFT)
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

  // TASK-017: Draft update methods
  const updateDraftField = useCallback(
    (field: keyof Omit<EditableExtractionDraft, 'line_items'>, value: string | number | null) => {
      setDraft((prev) => ({
        ...prev,
        [field]: value,
      }))
    },
    []
  )

  const updateDraftLineItem = useCallback(
    (index: number, updatedItem: Partial<LineItemCorrectionPayload>) => {
      setDraft((prev) => {
        const items = [...prev.line_items]
        if (index < 0 || index >= items.length) return prev

        const current = items[index]
        const merged = { ...current, ...updatedItem }

        // Automatically update amount if quantity or unit_price changed
        if ('quantity' in updatedItem || 'unit_price' in updatedItem) {
          const autoAmt = calculateLineItemAmount(merged.quantity, merged.unit_price)
          if (autoAmt !== null) {
            merged.amount = autoAmt
          }
        }

        items[index] = merged
        return { ...prev, line_items: items }
      })
    },
    []
  )

  const addDraftLineItem = useCallback(() => {
    setDraft((prev) => {
      const newLineNumber = prev.line_items.length + 1
      const newItem: LineItemCorrectionPayload = {
        line_number: newLineNumber,
        description: '',
        quantity: 1,
        unit_price: 0,
        amount: 0,
      }
      return {
        ...prev,
        line_items: [...prev.line_items, newItem],
      }
    })
  }, [])

  const removeDraftLineItem = useCallback((index: number) => {
    setDraft((prev) => {
      const items = prev.line_items.filter((_, i) => i !== index)
      // Renumber lines sequentially
      const renumbered = items.map((it, idx) => ({ ...it, line_number: idx + 1 }))
      return {
        ...prev,
        line_items: renumbered,
      }
    })
  }, [])

  const applyCalculatedSubtotal = useCallback(() => {
    setDraft((prev) => {
      const sum = calculateLineItemsSum(prev.line_items)
      return { ...prev, subtotal: sum }
    })
  }, [])

  const applyCalculatedTotal = useCallback(() => {
    setDraft((prev) => {
      const s = prev.subtotal !== null ? Number(prev.subtotal) : 0
      const t = prev.tax !== null ? Number(prev.tax) : 0
      const total = safeRound(s + t, 2)
      return { ...prev, total }
    })
  }, [])

  const resetDraft = useCallback(() => {
    initializeDraftFromDoc(document)
    setCorrectionError(null)
  }, [document, initializeDraftFromDoc])

  const cancelEditing = useCallback(() => {
    resetDraft()
    setIsEditMode(false)
  }, [resetDraft])

  // Track dirty state
  const { isDirty, dirtyFieldCount } = useMemo(() => {
    if (!document || !document.extraction) {
      return { isDirty: false, dirtyFieldCount: 0 }
    }
    const ext = document.extraction
    let count = 0

    const check = (val1: unknown, val2: unknown) => {
      const s1 = val1 === null || val1 === undefined ? '' : String(val1).trim()
      const s2 = val2 === null || val2 === undefined ? '' : String(val2).trim()
      return s1 !== s2
    }

    if (check(draft.invoice_number, ext.invoice_number)) count++
    if (check(draft.invoice_date, ext.invoice_date)) count++
    if (check(draft.due_date, ext.due_date)) count++
    if (check(draft.supplier_name, ext.supplier_name)) count++
    if (check(draft.supplier_address, ext.supplier_address)) count++
    if (check(draft.customer_name, ext.customer_name)) count++
    if (check(draft.customer_address, ext.customer_address)) count++
    if (check(draft.subtotal, ext.subtotal)) count++
    if (check(draft.tax, ext.tax)) count++
    if (check(draft.total, ext.total)) count++
    if (check(draft.currency, ext.currency)) count++

    // Line items dirty check
    const origItems = ext.line_items || []
    if (draft.line_items.length !== origItems.length) {
      count++
    } else {
      let itemsChanged = false
      for (let i = 0; i < origItems.length; i++) {
        const dIt = draft.line_items[i]
        const oIt = origItems[i]
        if (
          check(dIt.description, oIt.description) ||
          check(dIt.quantity, oIt.quantity) ||
          check(dIt.unit_price, oIt.unit_price) ||
          check(dIt.amount, oIt.amount)
        ) {
          itemsChanged = true
          break
        }
      }
      if (itemsChanged) count++
    }

    return { isDirty: count > 0, dirtyFieldCount: count }
  }, [document, draft])

  // Save manual corrections
  const saveCorrections = useCallback(
    async (operator = 'operator'): Promise<boolean> => {
      if (!documentId || !document || isSavingCorrection) return false

      setIsSavingCorrection(true)
      setCorrectionError(null)
      setCorrectionSuccessMessage(null)

      try {
        const payload: DocumentCorrectionPayload = {
          invoice_number: draft.invoice_number.trim() || null,
          invoice_date: draft.invoice_date.trim() || null,
          due_date: draft.due_date.trim() || null,
          supplier_name: draft.supplier_name.trim() || null,
          supplier_address: draft.supplier_address.trim() || null,
          customer_name: draft.customer_name.trim() || null,
          customer_address: draft.customer_address.trim() || null,
          subtotal: draft.subtotal !== null ? safeRound(draft.subtotal, 2) : null,
          tax: draft.tax !== null ? safeRound(draft.tax, 2) : null,
          total: draft.total !== null ? safeRound(draft.total, 2) : null,
          currency: draft.currency.trim() || 'USD',
          line_items: draft.line_items.map((it, idx) => ({
            id: it.id,
            line_number: idx + 1,
            description: it.description.trim() || 'Item',
            quantity: it.quantity !== null && it.quantity !== undefined ? safeRound(it.quantity, 4) : null,
            unit_price: it.unit_price !== null && it.unit_price !== undefined ? safeRound(it.unit_price, 4) : null,
            amount: it.amount !== null && it.amount !== undefined ? safeRound(it.amount, 2) : null,
          })),
          reason: draft.reason.trim() || 'Manual operator correction',
          operator,
        }

        const updatedDoc = await api.correctDocument(documentId, payload)
        setDocument(updatedDoc)
        initializeDraftFromDoc(updatedDoc)
        setIsEditMode(false)
        setCorrectionSuccessMessage('Corrections saved and audit log updated successfully.')
        return true
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to persist manual corrections'
        setCorrectionError(msg)
        return false
      } finally {
        setIsSavingCorrection(false)
      }
    },
    [documentId, document, draft, isSavingCorrection, initializeDraftFromDoc]
  )

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

    // TASK-017
    isEditMode,
    setIsEditMode,
    draft,
    isDirty,
    dirtyFieldCount,
    isSavingCorrection,
    correctionError,
    correctionSuccessMessage,
    updateDraftField,
    updateDraftLineItem,
    addDraftLineItem,
    removeDraftLineItem,
    applyCalculatedSubtotal,
    applyCalculatedTotal,
    saveCorrections,
    cancelEditing,
    resetDraft,

    refresh,
    reprocess,
  }
}
