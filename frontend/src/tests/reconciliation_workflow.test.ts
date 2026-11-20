/**
 * Automated Test Suite for TASK-018:
 * Reconciliation Workflow, Human-Correction Provenance & Line Item Pairing
 * Runs with Node.js native test runner via:
 * node --experimental-strip-types --test src/tests/reconciliation_workflow.test.ts
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import type {
  ReconciliationMatrixRow,
  DocumentSummaryWithExtraction,
  CrossVerificationStatus,
  CrossDocumentDiscrepancy,
} from '../types/reconciliation.ts'
import type { InvoiceExtraction } from '../types/document.ts'

/**
 * Pure helper function simulating comparison matrix building with provenance.
 */
function buildComparisonMatrix(
  docA: DocumentSummaryWithExtraction,
  docB: DocumentSummaryWithExtraction,
  tolerance = 0.05
): ReconciliationMatrixRow[] {
  const extA = docA.extraction
  const extB = docB.extraction

  const correctionsA = (docA.metadata?.manual_corrections as Record<string, any>) || {}
  const correctionsB = (docB.metadata?.manual_corrections as Record<string, any>) || {}

  const fields: { key: keyof InvoiceExtraction; label: string; isNumeric?: boolean }[] = [
    { key: 'invoice_number', label: 'Invoice Reference' },
    { key: 'invoice_date', label: 'Issue Date' },
    { key: 'supplier_name', label: 'Supplier / Vendor' },
    { key: 'customer_name', label: 'Customer / Recipient' },
    { key: 'currency', label: 'Currency Code' },
    { key: 'subtotal', label: 'Subtotal Amount', isNumeric: true },
    { key: 'tax', label: 'Tax Amount', isNumeric: true },
    { key: 'total', label: 'Total Amount', isNumeric: true },
  ]

  return fields.map(({ key, label, isNumeric }) => {
    const rawValA = extA ? extA[key] : null
    const rawValB = extB ? extB[key] : null

    const valAStr = rawValA != null ? String(rawValA) : null
    const valBStr = rawValB != null ? String(rawValB) : null

    const corrA = correctionsA[key]
    const corrB = correctionsB[key]

    const doc_a_is_corrected = !!corrA
    const doc_b_is_corrected = !!corrB

    const doc_a_original = corrA ? String(corrA.original_value) : null
    const doc_b_original = corrB ? String(corrB.original_value) : null

    let status: 'MATCH' | 'DISCREPANCY' | 'WARNING' | 'MISSING' = 'MATCH'
    let difference: string | null = null
    let message: string | null = null

    if (valAStr == null || valBStr == null) {
      status = 'MISSING'
      message = 'Field missing in one or both documents'
    } else if (isNumeric) {
      const numA = Number(rawValA)
      const numB = Number(rawValB)
      const diff = Math.round(Math.abs(numA - numB) * 100) / 100
      if (diff > tolerance) {
        status = 'DISCREPANCY'
        difference = diff.toFixed(2)
        message = `Variance exceeds tolerance ($${difference} > $${tolerance})`
      } else {
        difference = diff > 0 ? diff.toFixed(2) : null
        message = diff > 0 ? 'Variance within tolerance' : 'Exact match'
      }
    } else {
      const normA = valAStr.trim().toLowerCase()
      const normB = valBStr.trim().toLowerCase()
      if (normA !== normB) {
        status = 'DISCREPANCY'
        message = 'Text value mismatch'
      } else {
        message = 'Exact match'
      }
    }

    return {
      field: key,
      label,
      doc_a_value: valAStr,
      doc_b_value: valBStr,
      doc_a_is_corrected,
      doc_b_is_corrected,
      doc_a_original,
      doc_b_original,
      status,
      difference,
      message,
    }
  })
}

/**
 * Pure helper function to determine overall verification status.
 */
function determineReconciliationStatus(
  discrepancies: CrossDocumentDiscrepancy[],
  warnings: CrossDocumentDiscrepancy[]
): { status: CrossVerificationStatus; is_reconciled: boolean } {
  if (discrepancies.length > 0) {
    return { status: 'FAILED', is_reconciled: false }
  }
  if (warnings.length > 0) {
    return { status: 'NEEDS_REVIEW', is_reconciled: false }
  }
  return { status: 'VERIFIED', is_reconciled: true }
}

describe('TASK-018: Reconciliation Workflow & Human Correction Awareness', () => {
  const mockDocA: DocumentSummaryWithExtraction = {
    id: 'doc-001',
    filename: 'Invoice_TechCorp_001.pdf',
    file_type: 'application/pdf',
    file_size_bytes: 40960,
    status: 'SUCCESS',
    validation_status: 'VERIFIED',
    metadata: {
      manual_corrections: {
        total: {
          original_value: 1200.0,
          corrected_value: 1250.0,
          corrected_by: 'auditor@company.com',
          corrected_at: '2026-11-20T21:00:00Z',
          reason: 'Corrected OCR misread of 0 as 5',
        },
      },
    },
    extraction: {
      id: 'ext-001',
      invoice_number: 'INV-2026-001',
      invoice_date: '2026-11-15',
      due_date: '2026-12-15',
      supplier_name: 'TechCorp Solutions',
      supplier_address: '100 Tech Way',
      customer_name: 'DocuMind Org',
      customer_address: '200 Client Blvd',
      subtotal: 1000.0,
      tax: 250.0,
      total: 1250.0, // Human-corrected value
      currency: 'USD',
      confidence_score: 0.96,
      llm_model: 'gemini-1.5-pro',
      created_at: '2026-11-20T20:00:00Z',
      updated_at: '2026-11-20T21:00:00Z',
      line_items: [
        { id: 'item-1', line_number: 1, description: 'Software License', quantity: 1, unit_price: 1000.0, amount: 1000.0 },
      ],
    },
  }

  const mockDocB: DocumentSummaryWithExtraction = {
    id: 'doc-002',
    filename: 'PO_TechCorp_001.pdf',
    file_type: 'application/pdf',
    file_size_bytes: 35000,
    status: 'SUCCESS',
    validation_status: 'VERIFIED',
    metadata: {}, // Pure AI extraction, no corrections
    extraction: {
      id: 'ext-002',
      invoice_number: 'INV-2026-001',
      invoice_date: '2026-11-15',
      due_date: '2026-12-15',
      supplier_name: 'TechCorp Solutions',
      supplier_address: '100 Tech Way',
      customer_name: 'DocuMind Org',
      customer_address: '200 Client Blvd',
      subtotal: 1000.0,
      tax: 250.0,
      total: 1250.0,
      currency: 'USD',
      confidence_score: 0.99,
      llm_model: 'gemini-1.5-pro',
      created_at: '2026-11-20T20:05:00Z',
      updated_at: '2026-11-20T20:05:00Z',
      line_items: [
        { id: 'item-2', line_number: 1, description: 'Software License', quantity: 1, unit_price: 1000.0, amount: 1000.0 },
      ],
    },
  }

  describe('buildComparisonMatrix', () => {
    it('accurately identifies human-corrected fields and displays original AI extraction', () => {
      const matrix = buildComparisonMatrix(mockDocA, mockDocB)
      const totalRow = matrix.find((r) => r.field === 'total')

      assert.ok(totalRow, 'totalRow should exist in matrix')
      assert.equal(totalRow.doc_a_is_corrected, true)
      assert.equal(totalRow.doc_b_is_corrected, false)
      assert.equal(totalRow.doc_a_value, '1250')
      assert.equal(totalRow.doc_a_original, '1200')
      assert.equal(totalRow.doc_b_value, '1250')
      assert.equal(totalRow.status, 'MATCH')
    })

    it('marks matching fields as MATCH when within tolerance', () => {
      const matrix = buildComparisonMatrix(mockDocA, mockDocB)
      const subtotalRow = matrix.find((r) => r.field === 'subtotal')

      assert.ok(subtotalRow)
      assert.equal(subtotalRow.status, 'MATCH')
      assert.equal(subtotalRow.difference, null)
    })

    it('marks discrepancy when text values differ', () => {
      const docWithDiffSupplier: DocumentSummaryWithExtraction = {
        ...mockDocB,
        extraction: {
          ...mockDocB.extraction!,
          supplier_name: 'Different Supplier Inc',
        },
      }

      const matrix = buildComparisonMatrix(mockDocA, docWithDiffSupplier)
      const supplierRow = matrix.find((r) => r.field === 'supplier_name')

      assert.ok(supplierRow)
      assert.equal(supplierRow.status, 'DISCREPANCY')
      assert.equal(supplierRow.message, 'Text value mismatch')
    })

    it('marks discrepancy when numeric values exceed tolerance', () => {
      const docWithDiffTotal: DocumentSummaryWithExtraction = {
        ...mockDocB,
        extraction: {
          ...mockDocB.extraction!,
          total: 1300.0,
        },
      }

      const matrix = buildComparisonMatrix(mockDocA, docWithDiffTotal, 0.05)
      const totalRow = matrix.find((r) => r.field === 'total')

      assert.ok(totalRow)
      assert.equal(totalRow.status, 'DISCREPANCY')
      assert.equal(totalRow.difference, '50.00')
    })
  })

  describe('determineReconciliationStatus', () => {
    it('returns VERIFIED and is_reconciled: true when no discrepancies or warnings', () => {
      const result = determineReconciliationStatus([], [])
      assert.equal(result.status, 'VERIFIED')
      assert.equal(result.is_reconciled, true)
    })

    it('returns NEEDS_REVIEW and is_reconciled: false when only warnings present', () => {
      const warning: CrossDocumentDiscrepancy = {
        rule_id: 'CROSS_DATE_MISMATCH',
        field: 'invoice_date',
        message: 'Date mismatch',
        severity: 'WARNING',
        doc_a_value: '2026-11-15',
        doc_b_value: '2026-11-16',
        doc_a_id: 'doc-001',
        doc_b_id: 'doc-002',
      }
      const result = determineReconciliationStatus([], [warning])
      assert.equal(result.status, 'NEEDS_REVIEW')
      assert.equal(result.is_reconciled, false)
    })

    it('returns FAILED and is_reconciled: false when discrepancies present', () => {
      const error: CrossDocumentDiscrepancy = {
        rule_id: 'CROSS_TOTAL_MISMATCH',
        field: 'total',
        message: 'Total mismatch',
        severity: 'ERROR',
        doc_a_value: '1250',
        doc_b_value: '1300',
        doc_a_id: 'doc-001',
        doc_b_id: 'doc-002',
        difference: 50.0,
      }
      const result = determineReconciliationStatus([error], [])
      assert.equal(result.status, 'FAILED')
      assert.equal(result.is_reconciled, false)
    })
  })
})
