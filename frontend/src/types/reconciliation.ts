import type { InvoiceExtraction } from './document.ts'

export type CrossVerificationStatus = 'VERIFIED' | 'NEEDS_REVIEW' | 'FAILED' | 'PENDING'

export interface CrossDocumentDiscrepancy {
  rule_id: string
  field: string
  message: string
  severity: 'ERROR' | 'WARNING'
  doc_a_value: string | null
  doc_b_value: string | null
  doc_a_id: string
  doc_b_id: string
  difference?: string | number | null
}

export type MatrixMatchStatus = 'MATCH' | 'DISCREPANCY' | 'WARNING' | 'MISSING'

export interface ReconciliationMatrixRow {
  field: string
  label: string
  doc_a_value: string | null
  doc_b_value: string | null
  doc_a_is_corrected: boolean
  doc_b_is_corrected: boolean
  doc_a_original: string | null
  doc_b_original: string | null
  status: MatrixMatchStatus
  difference: string | null
  message: string | null
}

export interface DocumentSummaryWithExtraction {
  id: string
  filename: string
  file_type: string
  file_size_bytes: number
  status: string
  validation_status: string
  metadata: Record<string, unknown>
  extraction: InvoiceExtraction | null
}

export interface ReconciliationRecord {
  id: string
  doc_a: string
  doc_b: string
  doc_a_details?: DocumentSummaryWithExtraction
  doc_b_details?: DocumentSummaryWithExtraction
  status: CrossVerificationStatus
  is_reconciled: boolean
  discrepancies: CrossDocumentDiscrepancy[]
  warnings: CrossDocumentDiscrepancy[]
  fields_compared: string[]
  matched_items_count: number
  unmatched_items_count: number
  summary: string
  created_at: string
  comparison_matrix?: ReconciliationMatrixRow[]
}

export interface ReconciliationRequestPayload {
  doc_a_id: string
  doc_b_id: string
  tolerance?: number | string
  strict_reference_matching?: boolean
}
