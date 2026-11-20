/**
 * Centralized API Client for DocuMind-AI Frontend.
 * Interacts with Django REST Framework endpoints via Vite proxy (/api).
 */
import type {
  DashboardMetrics,
  DocumentCorrectionPayload,
  DocumentDetail,
  DocumentListItem,
  PaginatedResponse,
} from '../types/document.ts'
import type { DocumentStatusResponse, ReprocessResponse } from '../types/upload.ts'

const API_BASE = '/api'

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const headers = new Headers(options.headers || {})
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }

  try {
    const res = await fetch(url, { ...options, headers })
    if (!res.ok) {
      let errorBody: unknown = null
      try {
        errorBody = await res.json()
      } catch {
        errorBody = await res.text()
      }
      throw new ApiError(
        `API request failed with status ${res.status}: ${res.statusText}`,
        res.status,
        errorBody
      )
    }

    if (res.status === 204) {
      return {} as T
    }

    return (await res.json()) as T
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err
    }
    const message = err instanceof Error ? err.message : 'Network request failed'
    throw new ApiError(message, 0)
  }
}

export const api = {
  /**
   * Probes backend availability using the lightweight documents endpoint.
   */
  async checkBackendHealth(): Promise<{ isConnected: boolean; message: string }> {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 3500)
      const res = await fetch(`${API_BASE}/documents/?page_size=1`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      })
      clearTimeout(timeoutId)
      if (res.ok) {
        return { isConnected: true, message: 'Backend connected' }
      }
      return { isConnected: false, message: `Status ${res.status}` }
    } catch {
      return { isConnected: false, message: 'Backend offline' }
    }
  },

  /**
   * Uploads a document via multipart/form-data with byte-level progress reporting.
   * Uses XMLHttpRequest to track accurate file transmission progress.
   */
  uploadDocument(
    file: File,
    onProgress?: (percent: number) => void,
    abortSignal?: AbortSignal
  ): Promise<DocumentListItem> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      formData.append('file', file)

      if (abortSignal) {
        if (abortSignal.aborted) {
          reject(new ApiError('Upload cancelled by operator', 0))
          return
        }
        abortSignal.addEventListener('abort', () => {
          xhr.abort()
          reject(new ApiError('Upload cancelled by operator', 0))
        })
      }

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && event.total > 0) {
            const percent = Math.min(100, Math.round((event.loaded / event.total) * 100))
            onProgress(percent)
          }
        }
      }

      xhr.onload = () => {
        let responseData: unknown = null
        try {
          responseData = JSON.parse(xhr.responseText)
        } catch {
          responseData = xhr.responseText
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(responseData as DocumentListItem)
        } else {
          let errorMsg = `Upload failed with status ${xhr.status}`
          if (responseData && typeof responseData === 'object') {
            const errObj = responseData as Record<string, unknown>
            if (Array.isArray(errObj.file) && errObj.file.length > 0) {
              errorMsg = String(errObj.file[0])
            } else if (errObj.error) {
              errorMsg = String(errObj.error)
            } else if (errObj.detail) {
              errorMsg = String(errObj.detail)
            }
          }
          reject(new ApiError(errorMsg, xhr.status, responseData))
        }
      }

      xhr.onerror = () => {
        reject(new ApiError('Network connection failed during upload. Check backend connectivity.', 0))
      }

      xhr.ontimeout = () => {
        reject(new ApiError('Upload timed out. The server took too long to respond.', 0))
      }

      xhr.open('POST', `${API_BASE}/documents/`, true)
      xhr.setRequestHeader('Accept', 'application/json')
      xhr.timeout = 60000 // 60s timeout for upload
      xhr.send(formData)
    })
  },

  /**
   * Polls lightweight document status for active processing jobs.
   */
  async getDocumentStatus(id: string): Promise<DocumentStatusResponse> {
    return request<DocumentStatusResponse>(`/documents/${id}/status/`)
  },

  /**
   * Requests reprocessing / retry for a failed or existing document.
   */
  async reprocessDocument(id: string, force = false): Promise<ReprocessResponse> {
    return request<ReprocessResponse>(`/documents/${id}/reprocess/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ force }),
    })
  },

  /**
   * Fetches paginated document listing with optional status and search filters.
   */
  async getDocuments(params: {
    status?: string
    validation_status?: string
    file_type?: string
    search?: string
    ordering?: string
    page?: number
    page_size?: number
  } = {}): Promise<PaginatedResponse<DocumentListItem>> {
    const searchParams = new URLSearchParams()
    if (params.status) searchParams.set('status', params.status)
    if (params.validation_status) searchParams.set('validation_status', params.validation_status)
    if (params.file_type) searchParams.set('file_type', params.file_type)
    if (params.search) searchParams.set('search', params.search)
    if (params.ordering) searchParams.set('ordering', params.ordering)
    if (params.page) searchParams.set('page', String(params.page))
    if (params.page_size) searchParams.set('page_size', String(params.page_size))

    const query = searchParams.toString()
    return request<PaginatedResponse<DocumentListItem>>(`/documents/${query ? `?${query}` : ''}`)
  },

  /**
   * Fetches full detail for a single document including extraction and validations.
   */
  async getDocumentDetail(id: string): Promise<DocumentDetail> {
    return request<DocumentDetail>(`/documents/${id}/`)
  },

  /**
   * Persists manual operator corrections to document extraction and line items.
   */
  async correctDocument(
    id: string,
    payload: DocumentCorrectionPayload
  ): Promise<DocumentDetail> {
    return request<DocumentDetail>(`/documents/${id}/correct/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  },

  /**
   * Retrieves live metrics derived directly from real backend count queries.
   */
  async getDashboardMetrics(): Promise<DashboardMetrics> {
    try {
      const [totalRes, procRes, verRes, revRes, failRes] = await Promise.all([
        request<PaginatedResponse<DocumentListItem>>('/documents/?page_size=1'),
        request<PaginatedResponse<DocumentListItem>>('/documents/?status=PROCESSING&page_size=1'),
        request<PaginatedResponse<DocumentListItem>>('/documents/?validation_status=VERIFIED&page_size=1'),
        request<PaginatedResponse<DocumentListItem>>('/documents/?validation_status=NEEDS_REVIEW&page_size=1'),
        request<PaginatedResponse<DocumentListItem>>('/documents/?validation_status=FAILED&page_size=1'),
      ])

      return {
        total: totalRes.count,
        processing: procRes.count,
        verified: verRes.count,
        needsReview: revRes.count,
        failed: failRes.count,
      }
    } catch {
      // Return zeroed metrics if backend is unreachable
      return {
        total: 0,
        processing: 0,
        verified: 0,
        needsReview: 0,
        failed: 0,
      }
    }
  },

  /**
   * Retrieves the 5 most recent documents for the overview table.
   */
  async getRecentDocuments(limit = 5): Promise<DocumentListItem[]> {
    try {
      const res = await request<PaginatedResponse<DocumentListItem>>(
        `/documents/?ordering=-created_at&page_size=${limit}`
      )
      return res.results || []
    } catch {
      return []
    }
  },
}
