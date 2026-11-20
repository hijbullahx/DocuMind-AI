import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../services/api.ts'
import type { PreflightValidationResult, QueueItem, QueueSummary } from '../types/upload.ts'

const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024 // 25 MB
const ALLOWED_EXTENSIONS = new Set([
  'pdf',
  'png',
  'jpg',
  'jpeg',
  'tiff',
  'tif',
  'xlsx',
  'xls',
  'csv',
  'txt',
])

const CONCURRENCY_LIMIT = 2
const POLLING_INTERVAL_MS = 2000

export function validateFilePreflight(file: File): PreflightValidationResult {
  if (file.size === 0) {
    return { isValid: false, error: 'File is empty (0 bytes).' }
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    const maxMb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
    return { isValid: false, error: `File size exceeds maximum limit of ${maxMb} MB.` }
  }

  const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || '' : ''
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    const allowed = Array.from(ALLOWED_EXTENSIONS).sort().join(', ')
    return { isValid: false, error: `Unsupported format .${ext}. Allowed formats: ${allowed}.` }
  }

  return { isValid: true }
}

export function useUploadQueue(onDocumentCompleted?: () => void) {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [notifications, setNotifications] = useState<Array<{ id: string; message: string; type: 'info' | 'success' | 'warning' | 'danger' }>>([])

  // Track active upload abort controllers
  const activeAbortControllers = useRef<Map<string, AbortController>>(new Map())
  // Track active uploading IDs to enforce concurrency limit
  const activeUploadingIds = useRef<Set<string>>(new Set())

  const addNotification = useCallback(
    (message: string, type: 'info' | 'success' | 'warning' | 'danger' = 'info') => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
      setNotifications((prev) => [...prev, { id, message, type }])
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id))
      }, 5000)
    },
    []
  )

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  /**
   * Adds multiple files to the queue, applying preflight validation and duplicate guards.
   */
  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const fileList = Array.from(files)
      if (fileList.length === 0) return

      const newItems: QueueItem[] = []
      let duplicateCount = 0

      setQueue((prevQueue) => {
        const existingSignatures = new Set(
          prevQueue
            .filter((item) => item.clientStatus !== 'FAILED')
            .map((item) => `${item.filename}-${item.fileSizeBytes}`)
        )

        for (const file of fileList) {
          const sig = `${file.name}-${file.size}`
          if (existingSignatures.has(sig)) {
            duplicateCount++
            continue
          }

          existingSignatures.add(sig)
          const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || 'bin' : 'bin'
          const validation = validateFilePreflight(file)

          const item: QueueItem = {
            id: `client-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
            file,
            filename: file.name,
            fileSizeBytes: file.size,
            fileType: ext,
            clientStatus: validation.isValid ? 'PENDING' : 'FAILED',
            uploadProgress: 0,
            errorMessage: validation.error || null,
            retryCount: 0,
          }

          newItems.push(item)
        }

        return [...prevQueue, ...newItems]
      })

      if (duplicateCount > 0) {
        addNotification(
          `${duplicateCount} duplicate file(s) skipped. Already present in queue.`,
          'warning'
        )
      }

      const validCount = newItems.filter((i) => i.clientStatus === 'PENDING').length
      if (validCount > 0) {
        addNotification(`Queued ${validCount} file(s) for batch processing.`, 'info')
      }
    },
    [addNotification]
  )

  /**
   * Starts uploading a specific item using XMLHttpRequest.
   */
  const executeUpload = useCallback(
    async (item: QueueItem) => {
      activeUploadingIds.current.add(item.id)
      const controller = new AbortController()
      activeAbortControllers.current.set(item.id, controller)

      setQueue((prev) =>
        prev.map((q) =>
          q.id === item.id
            ? { ...q, clientStatus: 'UPLOADING', uploadProgress: 0, startedAt: Date.now(), errorMessage: null }
            : q
        )
      )

      try {
        const resultDoc = await api.uploadDocument(
          item.file,
          (percent) => {
            setQueue((prev) =>
              prev.map((q) => (q.id === item.id ? { ...q, uploadProgress: percent } : q))
            )
          },
          controller.signal
        )

        // Upload successfully transmitted and registered on backend
        setQueue((prev) =>
          prev.map((q) =>
            q.id === item.id
              ? {
                  ...q,
                  backendId: resultDoc.id,
                  backendStatus: resultDoc.status,
                  validationStatus: resultDoc.validation_status,
                  clientStatus: 'QUEUED',
                  uploadProgress: 100,
                  errorMessage: null,
                }
              : q
          )
        )
      } catch (err: unknown) {
        const errorMsg =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
            ? err.message
            : 'Upload failed due to network error.'

        setQueue((prev) =>
          prev.map((q) =>
            q.id === item.id
              ? {
                  ...q,
                  clientStatus: 'FAILED',
                  errorMessage: errorMsg,
                }
              : q
          )
        )
      } finally {
        activeUploadingIds.current.delete(item.id)
        activeAbortControllers.current.delete(item.id)
      }
    },
    []
  )

  /**
   * Upload scheduler loop: pulls next PENDING items while under concurrency limit.
   */
  useEffect(() => {
    const availableSlots = CONCURRENCY_LIMIT - activeUploadingIds.current.size
    if (availableSlots <= 0) return

    const pendingItems = queue.filter(
      (item) => item.clientStatus === 'PENDING' && !activeUploadingIds.current.has(item.id)
    )

    const itemsToStart = pendingItems.slice(0, availableSlots)
    for (const item of itemsToStart) {
      executeUpload(item)
    }
  }, [queue, executeUpload])

  /**
   * Status Polling Engine: Polls active backend jobs (QUEUED or PROCESSING).
   */
  useEffect(() => {
    const activeJobs = queue.filter(
      (item) =>
        item.backendId &&
        (item.clientStatus === 'QUEUED' ||
          item.clientStatus === 'PROCESSING' ||
          item.backendStatus === 'QUEUED' ||
          item.backendStatus === 'PROCESSING')
    )

    if (activeJobs.length === 0) return

    const intervalId = setInterval(async () => {
      for (const item of activeJobs) {
        if (!item.backendId) continue

        try {
          const statusRes = await api.getDocumentStatus(item.backendId)

          setQueue((prevQueue) =>
            prevQueue.map((q) => {
              if (q.id !== item.id) return q

              // Determine client display status based on true backend states
              let nextClientStatus = q.clientStatus
              let nextErrorMessage = statusRes.error_message || q.errorMessage

              if (statusRes.status === 'PROCESSING') {
                nextClientStatus = 'PROCESSING'
              } else if (statusRes.status === 'SUCCESS' || statusRes.status === 'PARTIAL_SUCCESS') {
                if (statusRes.validation_status === 'VERIFIED') {
                  nextClientStatus = 'SUCCESS'
                } else if (statusRes.validation_status === 'NEEDS_REVIEW') {
                  nextClientStatus = 'NEEDS_REVIEW'
                } else if (statusRes.validation_status === 'FAILED') {
                  nextClientStatus = 'FAILED'
                  nextErrorMessage = nextErrorMessage || 'Validation checks failed on this document.'
                } else {
                  nextClientStatus = 'SUCCESS'
                }
              } else if (statusRes.status === 'FAILED') {
                nextClientStatus = 'FAILED'
                nextErrorMessage = statusRes.error_message || 'Processing failed in Celery pipeline.'
              }

              const wasActive = q.clientStatus === 'QUEUED' || q.clientStatus === 'PROCESSING'
              const isTerminal =
                nextClientStatus === 'SUCCESS' ||
                nextClientStatus === 'NEEDS_REVIEW' ||
                nextClientStatus === 'FAILED'

              if (wasActive && isTerminal && onDocumentCompleted) {
                onDocumentCompleted()
              }

              return {
                ...q,
                backendStatus: statusRes.status,
                validationStatus: statusRes.validation_status,
                clientStatus: nextClientStatus,
                errorMessage: nextErrorMessage,
                completedAt: isTerminal ? Date.now() : q.completedAt,
              }
            })
          )
        } catch {
          // Ignore transient polling network drops
        }
      }
    }, POLLING_INTERVAL_MS)

    return () => clearInterval(intervalId)
  }, [queue, onDocumentCompleted])

  /**
   * Removes a file from the queue. If actively uploading, aborts network transfer.
   */
  const removeQueuedItem = useCallback((id: string) => {
    const controller = activeAbortControllers.current.get(id)
    if (controller) {
      controller.abort()
      activeAbortControllers.current.delete(id)
    }
    activeUploadingIds.current.delete(id)

    setQueue((prev) => prev.filter((item) => item.id !== id))
  }, [])

  /**
   * Retries an individual item.
   */
  const retryItem = useCallback(
    async (id: string) => {
      const item = queue.find((q) => q.id === id)
      if (!item) return

      if (item.backendId && item.backendStatus === 'FAILED') {
        // Retry existing backend document via reprocess endpoint
        try {
          await api.reprocessDocument(item.backendId, false)
          setQueue((prev) =>
            prev.map((q) =>
              q.id === id
                ? {
                    ...q,
                    clientStatus: 'QUEUED',
                    backendStatus: 'QUEUED',
                    errorMessage: null,
                    retryCount: q.retryCount + 1,
                  }
                : q
            )
          )
          addNotification(`Reprocessing initiated for ${item.filename}.`, 'info')
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Failed to trigger reprocessing.'
          addNotification(`Reprocess error: ${msg}`, 'danger')
        }
      } else {
        // Failed during upload or preflight; re-validate and restart upload
        const validation = validateFilePreflight(item.file)
        if (!validation.isValid) {
          setQueue((prev) =>
            prev.map((q) => (q.id === id ? { ...q, errorMessage: validation.error } : q))
          )
          addNotification(`Cannot retry: ${validation.error}`, 'danger')
          return
        }

        setQueue((prev) =>
          prev.map((q) =>
            q.id === id
              ? {
                  ...q,
                  clientStatus: 'PENDING',
                  uploadProgress: 0,
                  errorMessage: null,
                  retryCount: q.retryCount + 1,
                }
              : q
          )
        )
      }
    },
    [queue, addNotification]
  )

  /**
   * Retries all failed items.
   */
  const retryAllFailed = useCallback(() => {
    const failedItems = queue.filter((i) => i.clientStatus === 'FAILED')
    if (failedItems.length === 0) return

    for (const item of failedItems) {
      retryItem(item.id)
    }
    addNotification(`Retrying ${failedItems.length} failed item(s)...`, 'info')
  }, [queue, retryItem, addNotification])

  /**
   * Clears finished (SUCCESS or NEEDS_REVIEW) items from UI queue.
   */
  const clearCompleted = useCallback(() => {
    setQueue((prev) =>
      prev.filter((item) => item.clientStatus !== 'SUCCESS' && item.clientStatus !== 'NEEDS_REVIEW')
    )
  }, [])

  /**
   * Clears the entire queue from the UI without aborting active backend processing jobs.
   */
  const clearQueue = useCallback(() => {
    // Only abort active client-side network uploads
    for (const [id, controller] of activeAbortControllers.current.entries()) {
      controller.abort()
      activeUploadingIds.current.delete(id)
    }
    activeAbortControllers.current.clear()

    setQueue([])
    addNotification('Upload queue cleared.', 'info')
  }, [addNotification])

  // Summary Metrics Computation
  const summary: QueueSummary = {
    total: queue.length,
    pending: queue.filter((i) => i.clientStatus === 'PENDING').length,
    uploading: queue.filter((i) => i.clientStatus === 'UPLOADING').length,
    processing: queue.filter((i) => i.clientStatus === 'QUEUED' || i.clientStatus === 'PROCESSING').length,
    verified: queue.filter((i) => i.clientStatus === 'SUCCESS').length,
    needsReview: queue.filter((i) => i.clientStatus === 'NEEDS_REVIEW').length,
    failed: queue.filter((i) => i.clientStatus === 'FAILED').length,
  }

  return {
    queue,
    summary,
    notifications,
    addFiles,
    removeQueuedItem,
    retryItem,
    retryAllFailed,
    clearCompleted,
    clearQueue,
    dismissNotification,
  }
}
