/**
 * TypeScript Data Models mirroring Django REST Framework backend schemas.
 * Represents Document, Extraction, Line Items, Validation Findings, and Dashboard Metrics.
 */

export type DocumentStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'SUCCESS'
  | 'PARTIAL_SUCCESS'
  | 'FAILED'

export type ValidationStatus =
  | 'PENDING'
  | 'VERIFIED'
  | 'NEEDS_REVIEW'
  | 'FAILED'

export type ValidationSeverity =
  | 'ERROR'
  | 'WARNING'
  | 'INFO'

export interface LineItem {
  id: string
  line_number: number
  description: string
  quantity: number | null
  unit_price: number | null
  amount: number | null
}

export interface ValidationError {
  id: string
  rule_id: string
  field: string
  message: string
  severity: ValidationSeverity
  actual_value: string | null
  expected_value: string | null
  difference: number | null
  is_dismissed: boolean
  dismissed_by: string | null
  dismissed_at: string | null
}

export interface AuditLog {
  id: string
  action: string
  user_id: string | null
  field_name: string | null
  old_value: string | null
  new_value: string | null
  reason: string | null
  created_at: string
}

export interface InvoiceExtraction {
  id: string
  invoice_number: string | null
  invoice_date: string | null
  due_date: string | null
  supplier_name: string | null
  supplier_address: string | null
  customer_name: string | null
  customer_address: string | null
  subtotal: number | null
  tax: number | null
  total: number | null
  currency: string | null
  raw_text_evidence?: Record<string, unknown>
  confidence_score: number | null
  llm_model: string | null
  created_at: string
  updated_at: string
  line_items: LineItem[]
}

export interface DocumentListItem {
  id: string
  filename: string
  file_type: string
  file_size_bytes: number
  page_count: number
  status: DocumentStatus
  validation_status: ValidationStatus
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DocumentDetail extends DocumentListItem {
  raw_text: string | null
  metadata: Record<string, unknown>
  extraction: InvoiceExtraction | null
  validation_errors: ValidationError[]
  audit_logs: AuditLog[]
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface DashboardMetrics {
  total: number
  processing: number
  verified: number
  needsReview: number
  failed: number
}
