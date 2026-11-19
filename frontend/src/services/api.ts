/**
 * Centralized API Client for DocuMind-AI Frontend.
 * Interacts with Django REST Framework endpoints via Vite proxy (/api).
 */
import type {
  DashboardMetrics,
  DocumentDetail,
  DocumentListItem,
  PaginatedResponse,
} from '@/types/document'

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
