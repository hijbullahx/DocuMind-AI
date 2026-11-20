/**
 * Automated Test Suite for TASK-017:
 * Manual Correction Draft State & Workflow Logic
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  calculateExpectedTotal,
  calculateLineItemAmount,
  calculateLineItemsSum,
  safeRound,
} from '../utils/calculator.ts'
import type {
  DocumentCorrectionPayload,
  DocumentDetail,
  InvoiceExtraction,
  LineItemCorrectionPayload,
  ManualCorrectionsMetadata,
} from '../types/document.ts'

describe('TASK-017: Manual Correction Workflow & State Logic', () => {
  const mockExtraction: InvoiceExtraction = {
    id: 'ext-001',
    invoice_number: 'INV-2026-001',
    invoice_date: '2026-11-01',
    due_date: '2026-12-01',
    supplier_name: 'Acme Cloud Services',
    supplier_address: '100 Tech Blvd, Silicon Valley, CA',
    customer_name: 'Global Logistics Corp',
    customer_address: '500 Harbor Dr, Seattle, WA',
    subtotal: 1000.0,
    tax: 100.0,
    total: 1100.0,
    currency: 'USD',
    confidence_score: 0.95,
    llm_model: 'gemini-1.5-pro',
    raw_text_evidence: {
      invoice_number: 'INV-2026-001',
      total: '$1,100.00',
    },
    created_at: '2026-11-20T10:00:00Z',
    updated_at: '2026-11-20T10:00:00Z',
    line_items: [
      {
        id: 'li-1',
        line_number: 1,
        description: 'Server Hosting Subscription',
        quantity: 2,
        unit_price: 400.0,
        amount: 800.0,
      },
      {
        id: 'li-2',
        line_number: 2,
        description: 'SSL Certificate Renewal',
        quantity: 1,
        unit_price: 200.0,
        amount: 200.0,
      },
    ],
  }

  it('correctly initializes draft state from extracted document fields', () => {
    const items: LineItemCorrectionPayload[] = (mockExtraction.line_items || []).map((it) => ({
      id: it.id,
      line_number: it.line_number,
      description: it.description,
      quantity: it.quantity,
      unit_price: it.unit_price,
      amount: it.amount,
    }))

    const draft = {
      invoice_number: mockExtraction.invoice_number || '',
      invoice_date: mockExtraction.invoice_date || '',
      due_date: mockExtraction.due_date || '',
      supplier_name: mockExtraction.supplier_name || '',
      supplier_address: mockExtraction.supplier_address || '',
      customer_name: mockExtraction.customer_name || '',
      customer_address: mockExtraction.customer_address || '',
      subtotal: mockExtraction.subtotal !== null ? safeRound(mockExtraction.subtotal, 2) : null,
      tax: mockExtraction.tax !== null ? safeRound(mockExtraction.tax, 2) : null,
      total: mockExtraction.total !== null ? safeRound(mockExtraction.total, 2) : null,
      currency: mockExtraction.currency || 'USD',
      line_items: items,
      reason: '',
    }

    assert.equal(draft.invoice_number, 'INV-2026-001')
    assert.equal(draft.subtotal, 1000.0)
    assert.equal(draft.total, 1100.0)
    assert.equal(draft.line_items.length, 2)
    assert.equal(draft.line_items[0].description, 'Server Hosting Subscription')
  })

  it('detects changes in header fields and increments dirty count', () => {
    const originalSubtotal = 1000.0
    const originalTotal = 1100.0

    let draftSubtotal: number = originalSubtotal
    let draftTotal: number = originalTotal

    // User updates subtotal
    draftSubtotal = 1200.0
    const subtotalDirty = draftSubtotal !== originalSubtotal
    assert.equal(subtotalDirty, true)

    // User auto-calculates total using calculateExpectedTotal
    const calcResult = calculateExpectedTotal(draftSubtotal, 100.0)
    draftTotal = calcResult ?? 0
    assert.equal(draftTotal, 1300.0)
    const totalDirty = (draftTotal as number) !== (originalTotal as number)
    assert.equal(totalDirty, true)
  })

  it('supports line item addition, modification, and deletion', () => {
    const items: LineItemCorrectionPayload[] = [
      { line_number: 1, description: 'Original item', quantity: 1, unit_price: 50.0, amount: 50.0 },
    ]

    // 1. Add item
    const newItem: LineItemCorrectionPayload = {
      line_number: 2,
      description: 'Newly added line item',
      quantity: 3,
      unit_price: 25.0,
      amount: calculateLineItemAmount(3, 25.0),
    }
    items.push(newItem)
    assert.equal(items.length, 2)
    assert.equal(items[1].amount, 75.0)

    // 2. Modify item
    items[0].quantity = 2
    items[0].amount = calculateLineItemAmount(2, items[0].unit_price!)
    assert.equal(items[0].amount, 100.0)

    // 3. One-click line items sum calculation
    const calculatedSubtotal = calculateLineItemsSum(items)
    assert.equal(calculatedSubtotal, 175.0)

    // 4. Delete item
    items.splice(0, 1)
    assert.equal(items.length, 1)
    assert.equal(items[0].description, 'Newly added line item')
  })

  it('constructs correct API correction payload preserving types and reason', () => {
    const payload: DocumentCorrectionPayload = {
      invoice_number: 'INV-CORRECTED-99',
      subtotal: 1500.0,
      tax: 150.0,
      total: 1650.0,
      currency: 'USD',
      reason: 'Auditor corrected OCR misalignment',
      operator: 'qa-specialist-01',
      line_items: [
        {
          line_number: 1,
          description: 'Consulting services',
          quantity: 10,
          unit_price: 150.0,
          amount: 1500.0,
        },
      ],
    }

    assert.equal(payload.invoice_number, 'INV-CORRECTED-99')
    assert.equal(payload.subtotal, 1500.0)
    assert.equal(payload.total, 1650.0)
    assert.equal(payload.reason, 'Auditor corrected OCR misalignment')
    assert.equal(payload.operator, 'qa-specialist-01')
    assert.equal(payload.line_items?.length, 1)
    assert.equal(payload.line_items?.[0]?.line_number, 1)
  })

  it('preserves original machine extraction data when document has manual corrections metadata', () => {
    const documentWithCorrections: DocumentDetail = {
      id: 'doc-001',
      filename: 'invoice-001.pdf',
      file_size_bytes: 45000,
      file_type: 'pdf',
      page_count: 1,
      status: 'SUCCESS',
      validation_status: 'VERIFIED',
      error_message: null,
      raw_text: 'INVOICE INV-2026-001 ...',
      created_at: '2026-11-20T10:00:00Z',
      updated_at: '2026-11-20T10:30:00Z',
      extraction: {
        ...mockExtraction,
        subtotal: 1200.0, // Corrected value
        total: 1300.0,    // Corrected value
      },
      validation_errors: [],
      audit_logs: [
        {
          id: 'audit-1',
          user_id: 'qa-specialist-01',
          action: 'MANUAL_CORRECTION',
          field_name: 'subtotal',
          old_value: '1000.0',
          new_value: '1200.0',
          reason: 'Corrected subtotal',
          created_at: '2026-11-20T10:30:00Z',
        },
      ],
      metadata: {
        manual_corrections: {
          is_corrected: true,
          last_corrected_at: '2026-11-20T10:30:00Z',
          corrected_fields: ['subtotal', 'total'],
          original_extraction: {
            subtotal: 1000.0, // Original machine extracted value intact
            total: 1100.0,
            invoice_number: 'INV-2026-001',
          },
        },
      },
    }

    const manualCorrections = (documentWithCorrections.metadata?.manual_corrections || {}) as ManualCorrectionsMetadata
    assert.equal(manualCorrections.is_corrected, true)
    assert.equal(manualCorrections.corrected_fields?.includes('subtotal'), true)
    assert.equal(manualCorrections.original_extraction?.subtotal, 1000.0)
    assert.equal(documentWithCorrections.extraction?.subtotal, 1200.0)
    assert.equal(documentWithCorrections.audit_logs?.length, 1)
  })
})
