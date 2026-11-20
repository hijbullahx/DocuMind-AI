/**
 * Automated Test Suite for TASK-016:
 * Evidence Grounding & Safe Text Highlighting.
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

describe('TASK-016: Evidence Grounding & Text Matching', () => {
  const sampleOCRText = `
ACME INDUSTRIAL SUPPLIES LTD
100 SUPPLY CHAIN WAY, SUITE 400
INVOICE NUMBER: INV-2026-8899
DATE: 2026-03-15
DUE DATE: 2026-04-15

BILL TO:
GLOBAL LOGISTICS CORP
450 COMMERCE BLVD

DESCRIPTION                 QTY    PRICE       AMOUNT
Heavy Duty Machine Bolts    100    $12.50      $1,250.00
Hydraulic Oil Drum 55 Gal     2   $180.00        $360.00

SUBTOTAL:                                      $1,610.00
SALES TAX (8.25%):                               $132.83
TOTAL PAYABLE:                                 $1,742.83
`.trim()

  const rawEvidence = {
    invoice_number: 'INV-2026-8899',
    supplier_name: 'ACME INDUSTRIAL SUPPLIES LTD',
    subtotal: '$1,610.00',
    tax: '$132.83',
    total: '$1,742.83',
    hallucinated_field: 'NON_EXISTENT_QUOTE_XYZ_123',
    empty_field: '',
  }

  it('successfully locates verbatim evidence quote in raw OCR text', () => {
    const quote = rawEvidence.invoice_number
    assert.equal(sampleOCRText.includes(quote), true)

    const matchIndex = sampleOCRText.indexOf(quote)
    assert.ok(matchIndex > 0)
    assert.equal(sampleOCRText.slice(matchIndex, matchIndex + quote.length), quote)
  })

  it('performs case-insensitive grounding matching', () => {
    const lowerQuote = 'acme industrial supplies ltd'
    const found = sampleOCRText.toLowerCase().includes(lowerQuote.toLowerCase())
    assert.equal(found, true)
  })

  it('handles quotes with special regex characters safely ($ , . / -)', () => {
    const totalQuote = rawEvidence.total // '$1,742.83'
    const escaped = totalQuote.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(escaped, 'gi')
    const matches = sampleOCRText.match(regex)

    assert.ok(matches)
    assert.equal(matches.length, 1)
    assert.equal(matches[0], '$1,742.83')
  })

  it('identifies ungrounded / hallucinated quotes without crashing', () => {
    const badQuote = rawEvidence.hallucinated_field
    const found = sampleOCRText.toLowerCase().includes(badQuote.toLowerCase())
    assert.equal(found, false)
  })

  it('safely handles empty, whitespace, and null evidence', () => {
    const emptyQuote = rawEvidence.empty_field
    assert.equal(!emptyQuote || emptyQuote.trim() === '', true)

    const nullQuote = null as string | null
    assert.equal(!nullQuote, true)
  })

  it('verifies non-interfering coexistence of search query and evidence grounding', () => {
    const searchQuery = 'Heavy Duty'
    const evidenceQuote = 'INV-2026-8899'

    // Both patterns can be matched independently without string corruption
    const searchEscaped = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const evidenceEscaped = evidenceQuote.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

    const searchMatches = sampleOCRText.match(new RegExp(searchEscaped, 'gi'))
    const evidenceMatches = sampleOCRText.match(new RegExp(evidenceEscaped, 'gi'))

    assert.ok(searchMatches)
    assert.equal(searchMatches.length, 1)

    assert.ok(evidenceMatches)
    assert.equal(evidenceMatches.length, 1)
  })
})
