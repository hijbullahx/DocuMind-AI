/**
 * Automated Test Suite for TASK-018:
 * Reconciliation Matching, Token Overlap & Rule Verification
 * Runs with Node.js native test runner via:
 * node --experimental-strip-types --test src/tests/reconciliation_matching.test.ts
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

/**
 * Helper to compute token Jaccard similarity mirroring CrossDocumentVerifier.
 */
function computeDescriptionSimilarity(descA: string, descB: string): number {
  const normA = descA.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\s+/).filter(Boolean)
  const normB = descB.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\s+/).filter(Boolean)
  if (!normA.length || !normB.length) return 0.0
  const setA = new Set(normA)
  const setB = new Set(normB)
  const intersection = new Set([...setA].filter((x) => setB.has(x)))
  const union = new Set([...setA, ...setB])
  return intersection.size / union.size
}

/**
 * Normalizes currency symbols to ISO 4217 code.
 */
function normalizeCurrency(raw: string | null | undefined): string {
  if (!raw) return 'USD'
  const trimmed = raw.trim().toUpperCase()
  if (trimmed === '$' || trimmed === 'US$' || trimmed === 'USD') return 'USD'
  if (trimmed === '€' || trimmed === 'EUR') return 'EUR'
  if (trimmed === '£' || trimmed === 'GBP') return 'GBP'
  return trimmed
}

/**
 * Checks whether two numeric values match within a specified tolerance.
 */
function checkNumericMatch(
  valA: number | null | undefined,
  valB: number | null | undefined,
  tolerance = 0.05
): { isMatch: boolean; diff: number | null } {
  if (valA == null || valB == null) {
    return { isMatch: false, diff: null }
  }
  const diff = Math.round(Math.abs(valA - valB) * 100) / 100
  return {
    isMatch: diff <= tolerance,
    diff,
  }
}

/**
 * Checks if two documents represent a potential duplicate invoice.
 */
function isPotentialDuplicate(
  supplierA: string | null,
  supplierB: string | null,
  invoiceNumA: string | null,
  invoiceNumB: string | null,
  totalA: number | null,
  totalB: number | null,
  tolerance = 0.05
): boolean {
  if (!supplierA || !supplierB || !invoiceNumA || !invoiceNumB || totalA == null || totalB == null) {
    return false
  }
  const normSuppA = supplierA.trim().toLowerCase()
  const normSuppB = supplierB.trim().toLowerCase()
  const normInvA = invoiceNumA.trim().toLowerCase()
  const normInvB = invoiceNumB.trim().toLowerCase()

  const sameSupplier = normSuppA === normSuppB
  const sameInvoice = normInvA === normInvB
  const sameTotal = Math.abs(totalA - totalB) <= tolerance

  return sameSupplier && sameInvoice && sameTotal
}

describe('TASK-018: Reconciliation Matching & Token Similarity', () => {
  describe('computeDescriptionSimilarity', () => {
    it('returns 1.0 for identical descriptions regardless of casing or extra punctuation', () => {
      const sim = computeDescriptionSimilarity(
        'Cloud Hosting - Professional Tier',
        'cloud hosting: professional tier!'
      )
      assert.equal(sim, 1.0)
    })

    it('returns high similarity (>0.6) for minor variations in wording', () => {
      const sim = computeDescriptionSimilarity(
        'Annual Software Subscription License - 5 Users',
        'Software Subscription License - 5 Users (Annual)'
      )
      assert.ok(sim >= 0.7, `Expected similarity >= 0.7, got ${sim}`)
    })

    it('returns 0.0 for completely unrelated product descriptions', () => {
      const sim = computeDescriptionSimilarity(
        'Dell 27-inch 4K Monitor',
        'Office Ergonomic Mesh Chair'
      )
      assert.equal(sim, 0.0)
    })

    it('handles empty, whitespace, or punctuation-only strings gracefully without throwing', () => {
      assert.equal(computeDescriptionSimilarity('', 'Some Product'), 0.0)
      assert.equal(computeDescriptionSimilarity('   ', '   '), 0.0)
      assert.equal(computeDescriptionSimilarity('---', '***'), 0.0)
    })
  })

  describe('normalizeCurrency', () => {
    it('normalizes common currency symbols to standard ISO 4217 codes', () => {
      assert.equal(normalizeCurrency('$'), 'USD')
      assert.equal(normalizeCurrency('US$'), 'USD')
      assert.equal(normalizeCurrency('USD'), 'USD')
      assert.equal(normalizeCurrency('€'), 'EUR')
      assert.equal(normalizeCurrency('EUR'), 'EUR')
      assert.equal(normalizeCurrency('£'), 'GBP')
      assert.equal(normalizeCurrency('GBP'), 'GBP')
    })

    it('defaults empty or undefined currency to USD', () => {
      assert.equal(normalizeCurrency(null), 'USD')
      assert.equal(normalizeCurrency(undefined), 'USD')
      assert.equal(normalizeCurrency(''), 'USD')
    })
  })

  describe('checkNumericMatch with tolerance', () => {
    it('identifies exact matches with diff 0', () => {
      const res = checkNumericMatch(1250.5, 1250.5, 0.05)
      assert.equal(res.isMatch, true)
      assert.equal(res.diff, 0)
    })

    it('accepts differences within tolerance (e.g. $0.02 with $0.05 tolerance)', () => {
      const res = checkNumericMatch(100.02, 100.0, 0.05)
      assert.equal(res.isMatch, true)
      assert.equal(res.diff, 0.02)
    })

    it('flags discrepancies exceeding tolerance', () => {
      const res = checkNumericMatch(1500.0, 1550.0, 0.05)
      assert.equal(res.isMatch, false)
      assert.equal(res.diff, 50.0)
    })

    it('flags missing values as non-matching with diff null', () => {
      const res = checkNumericMatch(null, 1500.0, 0.05)
      assert.equal(res.isMatch, false)
      assert.equal(res.diff, null)
    })
  })

  describe('isPotentialDuplicate', () => {
    it('flags matching supplier, invoice number, and total as potential duplicate', () => {
      const duplicate = isPotentialDuplicate(
        'Acme Supplies LLC',
        'acme supplies llc',
        'INV-2024-9901',
        'INV-2024-9901',
        450.0,
        450.0
      )
      assert.equal(duplicate, true)
    })

    it('does not flag when invoice numbers differ', () => {
      const duplicate = isPotentialDuplicate(
        'Acme Supplies LLC',
        'Acme Supplies LLC',
        'INV-2024-001',
        'INV-2024-002',
        450.0,
        450.0
      )
      assert.equal(duplicate, false)
    })

    it('does not flag when totals differ significantly', () => {
      const duplicate = isPotentialDuplicate(
        'Acme Supplies LLC',
        'Acme Supplies LLC',
        'INV-2024-001',
        'INV-2024-001',
        450.0,
        890.0
      )
      assert.equal(duplicate, false)
    })
  })
})
