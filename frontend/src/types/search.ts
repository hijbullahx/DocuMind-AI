import type { DocumentStatus, ValidationStatus } from './document.ts'

export type SearchMatchedField =
  | 'INVOICE_NUMBER'
  | 'FILENAME'
  | 'SUPPLIER_NAME'
  | 'CUSTOMER_NAME'
  | 'LINE_ITEM'
  | 'OCR_CONTENT'
  | 'METADATA'

export interface SearchResultItem {
  id: string
  filename: string
  status: DocumentStatus
  validation_status: ValidationStatus
  file_type: string
  file_size_bytes: number
  created_at: string
  invoice_number?: string | null
  invoice_date?: string | null
  supplier_name?: string | null
  customer_name?: string | null
  total?: string | null
  currency?: string | null
  snippet: string
  matched_field: SearchMatchedField
  matched_field_label: string
  search_rank?: number | null
}

export interface SearchResponse {
  query: string
  count: number
  page: number
  page_size: number
  total_pages: number
  results: SearchResultItem[]
}

export interface SearchQueryParams {
  q: string
  status?: string
  validation_status?: string
  file_type?: string
  date_from?: string
  date_to?: string
  supplier?: string
  customer?: string
  page?: number
  page_size?: number
}
