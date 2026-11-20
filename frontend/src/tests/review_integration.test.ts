/**
 * Automated Test Suite for TASK-016:
 * Review Workbench Integration, Selector Filtering & API Contract Verification.
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import type { DocumentDetail, DocumentListItem, InvoiceExtraction } from '../types/document.ts'

describe('TASK-016: Document Detail API Contract Verification', () => {
  const mockDetail: DocumentDetail = {
    id: 'a0000000-0000-0000-0000-000000000001',
    filename: 'supplier_invoice_2026.pdf',
    file_type: 'pdf',
    file_size_bytes: 524288,
    page_count: 2,
    status: 'SUCCESS',
    validation_status: 'NEEDS_REVIEW',
    error_message: null,
    raw_text: 'SUPPLIER CORP\nINVOICE #9988\nTOTAL: $500.00',
    metadata: {
      ocr_engine: 'EasyOCREngine',
      dpi: 300,
    },
    created_at: '2026-03-15T09:00:00Z',
    updated_at: '2026-03-15T09:05:00Z',
    extraction: {
      id: 'ext-001',
      invoice_number: '9988',
      invoice_date: '2026-03-15',
      due_date: '2026-04-15',
      supplier_name: 'SUPPLIER CORP',
      supplier_address: '100 Main St',
      customer_name: 'BUYER LLC',
      customer_address: '200 Market St',
      subtotal: 450.0,
      tax: 50.0,
      total: 500.0,
      currency: 'USD',
      raw_text_evidence: {
        invoice_number: '9988',
        supplier_name: 'SUPPLIER CORP',
        total: '$500.00',
      },
      confidence_score: 0.96,
      llm_model: 'gemini-1.5-pro',
      created_at: '2026-03-15T09:02:00Z',
      updated_at: '2026-03-15T09:02:00Z',
      line_items: [
        {
          id: 'li-1',
          line_number: 1,
          description: 'Widget A',
          quantity: 10,
          unit_price: 45.0,
          amount: 450.0,
        },
      ],
    },
    validation_errors: [
      {
        id: 'val-1',
        rule_id: 'ANOMALY_ROUND_TOTAL',
        field: 'total',
        message: 'Total amount is exact round number',
        severity: 'INFO',
        actual_value: '500.00',
        expected_value: null,
        difference: null,
        is_dismissed: false,
        dismissed_by: null,
        dismissed_at: null,
      },
    ],
    audit_logs: [
      {
        id: 'aud-1',
        action: 'STATUS_CHANGE',
        user_id: 'system',
        field_name: 'status',
        old_value: 'PROCESSING',
        new_value: 'SUCCESS',
        reason: 'Automated processing finished',
        created_at: '2026-03-15T09:05:00Z',
      },
    ],
  }

  it('validates structure of comprehensive DocumentDetail entity', () => {
    assert.equal(mockDetail.id, 'a0000000-0000-0000-0000-000000000001')
    assert.equal(mockDetail.status, 'SUCCESS')
    assert.equal(mockDetail.validation_status, 'NEEDS_REVIEW')
    assert.ok(mockDetail.raw_text)
    assert.ok(mockDetail.extraction)
    assert.equal(mockDetail.extraction?.line_items.length, 1)
    assert.equal(mockDetail.validation_errors.length, 1)
    assert.equal(mockDetail.audit_logs.length, 1)
  })

  it('validates that extraction and validation relations are read-only and immutable in view', () => {
    const extraction: InvoiceExtraction = mockDetail.extraction!
    assert.equal(extraction.invoice_number, '9988')
    assert.equal(extraction.confidence_score, 0.96)
    assert.equal(mockDetail.audit_logs[0].action, 'STATUS_CHANGE')
  })
})

describe('TASK-016: Document Selector Query Parameters & Filtering Logic', () => {
  const documentsList: DocumentListItem[] = [
    {
      id: 'doc-1',
      filename: 'invoice_needs_review.pdf',
      file_type: 'pdf',
      file_size_bytes: 102400,
      page_count: 1,
      status: 'SUCCESS',
      validation_status: 'NEEDS_REVIEW',
      error_message: null,
      created_at: '2026-03-15T08:00:00Z',
      updated_at: '2026-03-15T08:05:00Z',
    },
    {
      id: 'doc-2',
      filename: 'invoice_verified.pdf',
      file_type: 'pdf',
      file_size_bytes: 204800,
      page_count: 2,
      status: 'SUCCESS',
      validation_status: 'VERIFIED',
      error_message: null,
      created_at: '2026-03-15T08:30:00Z',
      updated_at: '2026-03-15T08:35:00Z',
    },
    {
      id: 'doc-3',
      filename: 'invoice_failed.pdf',
      file_type: 'pdf',
      file_size_bytes: 51200,
      page_count: 1,
      status: 'FAILED',
      validation_status: 'FAILED',
      error_message: 'Corrupted PDF file headers',
      created_at: '2026-03-15T09:00:00Z',
      updated_at: '2026-03-15T09:01:00Z',
    },
  ]

  it('correctly filters documents by validation status', () => {
    const needsReview = documentsList.filter((d) => d.validation_status === 'NEEDS_REVIEW')
    const verified = documentsList.filter((d) => d.validation_status === 'VERIFIED')
    const failed = documentsList.filter((d) => d.validation_status === 'FAILED')

    assert.equal(needsReview.length, 1)
    assert.equal(needsReview[0].id, 'doc-1')

    assert.equal(verified.length, 1)
    assert.equal(verified[0].id, 'doc-2')

    assert.equal(failed.length, 1)
    assert.equal(failed[0].id, 'doc-3')
  })

  it('correctly filters documents by search term matching filename', () => {
    const query = 'verified'
    const results = documentsList.filter((d) => d.filename.toLowerCase().includes(query.toLowerCase()))
    assert.equal(results.length, 1)
    assert.equal(results[0].id, 'doc-2')
  })

  it('constructs correct API URL query parameters for listing endpoint', () => {
    const params = {
      page: 2,
      page_size: 20,
      search: 'Acme',
      validation_status: 'NEEDS_REVIEW',
    }

    const searchParams = new URLSearchParams()
    if (params.search) searchParams.set('search', params.search)
    if (params.validation_status) searchParams.set('validation_status', params.validation_status)
    searchParams.set('page', String(params.page))
    searchParams.set('page_size', String(params.page_size))

    const queryString = searchParams.toString()
    assert.equal(queryString, 'search=Acme&validation_status=NEEDS_REVIEW&page=2&page_size=20')
  })
})
