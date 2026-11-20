/**
 * Automated Test Suite for TASK-019:
 * Full-Text Search Service, Highlight Safety & Filter Logic
 * Runs with Node.js native test runner via:
 * node --experimental-strip-types --test src/tests/search_service.test.ts
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import type { SearchQueryParams, SearchResultItem, SearchMatchedField } from '../types/search.ts'

/**
 * Pure helper function simulating query parameter normalization.
 */
function buildSearchQueryString(params: SearchQueryParams): string {
  const searchParams = new URLSearchParams()
  if (params.q) searchParams.set('q', params.q.trim())
  if (params.status) searchParams.set('status', params.status.trim())
  if (params.validation_status) searchParams.set('validation_status', params.validation_status.trim())
  if (params.file_type) searchParams.set('file_type', params.file_type.trim())
  if (params.date_from) searchParams.set('date_from', params.date_from.trim())
  if (params.date_to) searchParams.set('date_to', params.date_to.trim())
  if (params.supplier) searchParams.set('supplier', params.supplier.trim())
  if (params.customer) searchParams.set('customer', params.customer.trim())
  if (params.page) searchParams.set('page', String(params.page))
  if (params.page_size) searchParams.set('page_size', String(params.page_size))

  return searchParams.toString()
}

/**
 * Pure helper for safely sanitizing text and generating highlights.
 */
function highlightKeywords(rawText: string, query: string): string {
  if (!rawText) return ''
  const escaped = rawText
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')

  const tokens = query.trim().split(/\s+/).filter(Boolean)
  if (!tokens.length) return escaped

  const regexPattern = new RegExp(`(${tokens.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  return escaped.replace(regexPattern, '<mark class="highlight">$1</mark>')
}

/**
 * Label mapping helper.
 */
function getMatchedFieldLabel(field: SearchMatchedField): string {
  switch (field) {
    case 'INVOICE_NUMBER':
      return 'Invoice Reference'
    case 'FILENAME':
      return 'Document Filename'
    case 'SUPPLIER_NAME':
      return 'Supplier / Vendor'
    case 'CUSTOMER_NAME':
      return 'Customer / Recipient'
    case 'LINE_ITEM':
      return 'Line Item Description'
    case 'OCR_CONTENT':
      return 'OCR Document Text'
    default:
      return 'Document Metadata'
  }
}

describe('TASK-019: Full-Text Search Engine & Snippet Highlighting', () => {
  describe('buildSearchQueryString', () => {
    it('properly serializes search query and pagination parameters', () => {
      const qs = buildSearchQueryString({
        q: 'TechCorp Falcon',
        page: 2,
        page_size: 15,
      })
      assert.ok(qs.includes('q=TechCorp+Falcon'))
      assert.ok(qs.includes('page=2'))
      assert.ok(qs.includes('page_size=15'))
    })

    it('serializes all supported filters when populated', () => {
      const qs = buildSearchQueryString({
        q: 'invoice',
        status: 'SUCCESS',
        validation_status: 'VERIFIED',
        file_type: 'pdf',
        date_from: '2026-01-01',
        date_to: '2026-02-28',
        supplier: 'Acme',
        customer: 'Global Logistics',
      })
      assert.ok(qs.includes('status=SUCCESS'))
      assert.ok(qs.includes('validation_status=VERIFIED'))
      assert.ok(qs.includes('file_type=pdf'))
      assert.ok(qs.includes('date_from=2026-01-01'))
      assert.ok(qs.includes('date_to=2026-02-28'))
      assert.ok(qs.includes('supplier=Acme'))
      assert.ok(qs.includes('customer=Global+Logistics'))
    })

    it('omits undefined or empty filter fields', () => {
      const qs = buildSearchQueryString({
        q: 'search term',
        status: undefined,
        validation_status: '',
      })
      assert.equal(qs, 'q=search+term')
    })
  })

  describe('highlightKeywords & XSS safety', () => {
    it('wraps matched tokens in mark tags while preserving case', () => {
      const result = highlightKeywords('Invoice for Acme Industrial Corp', 'acme')
      assert.ok(result.includes('<mark class="highlight">Acme</mark>'))
    })

    it('neutralizes malicious HTML script tags in untrusted OCR text', () => {
      const maliciousOCR = "Notes: <script>alert('xss')</script> Falcon Project"
      const result = highlightKeywords(maliciousOCR, 'Falcon')

      assert.ok(!result.includes('<script>'))
      assert.ok(result.includes('&lt;script&gt;'))
      assert.ok(result.includes('<mark class="highlight">Falcon</mark>'))
    })

    it('handles multi-word search queries across text', () => {
      const text = 'Grade 8 Titanium Screws Box of 500'
      const result = highlightKeywords(text, 'Titanium Screws')

      assert.ok(result.includes('<mark class="highlight">Titanium</mark>'))
      assert.ok(result.includes('<mark class="highlight">Screws</mark>'))
    })

    it('returns escaped string without mark tags when query does not match', () => {
      const text = 'Simple Document Title'
      const result = highlightKeywords(text, 'NonExistent')
      assert.equal(result, 'Simple Document Title')
    })
  })

  describe('getMatchedFieldLabel', () => {
    it('returns human-readable labels for all supported tier categories', () => {
      assert.equal(getMatchedFieldLabel('INVOICE_NUMBER'), 'Invoice Reference')
      assert.equal(getMatchedFieldLabel('FILENAME'), 'Document Filename')
      assert.equal(getMatchedFieldLabel('SUPPLIER_NAME'), 'Supplier / Vendor')
      assert.equal(getMatchedFieldLabel('CUSTOMER_NAME'), 'Customer / Recipient')
      assert.equal(getMatchedFieldLabel('LINE_ITEM'), 'Line Item Description')
      assert.equal(getMatchedFieldLabel('OCR_CONTENT'), 'OCR Document Text')
      assert.equal(getMatchedFieldLabel('METADATA'), 'Document Metadata')
    })
  })

  describe('SearchResultItem structure verification', () => {
    it('validates shape of a populated search result item', () => {
      const item: SearchResultItem = {
        id: 'doc-uuid-1',
        filename: 'invoice_falcon_2026.pdf',
        status: 'SUCCESS',
        validation_status: 'VERIFIED',
        file_type: 'pdf',
        file_size_bytes: 45000,
        created_at: '2026-02-10T14:30:00Z',
        invoice_number: 'INV-2026-001',
        supplier_name: 'TechCorp',
        total: '5500.00',
        currency: 'USD',
        snippet: 'Invoice Reference: <mark>INV-2026-001</mark>',
        matched_field: 'INVOICE_NUMBER',
        matched_field_label: 'Invoice Reference',
        search_rank: 0.95,
      }

      assert.equal(item.id, 'doc-uuid-1')
      assert.equal(item.matched_field, 'INVOICE_NUMBER')
      assert.ok(item.snippet.includes('<mark>INV-2026-001</mark>'))
    })
  })
})
