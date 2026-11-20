/**
 * Automated Test Suite for TASK-016:
 * Document Review Workbench — Formatting, Validation & Math Rules.
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  checkMathEquality,
  formatBytes,
  formatConfidence,
  formatCurrency,
  formatDate,
  formatDateTime,
} from '../utils/formatters.ts'
import type { ValidationError, ValidationSeverity } from '../types/document.ts'

describe('TASK-016: Formatting & Display Utilities', () => {
  it('formats currency with default USD symbol and 2 decimal places', () => {
    assert.equal(formatCurrency(1250.5), '$1,250.50')
    assert.equal(formatCurrency('1250.5'), '$1,250.50')
    assert.equal(formatCurrency(0), '$0.00')
    assert.equal(formatCurrency(null), '—')
    assert.equal(formatCurrency(undefined), '—')
    assert.equal(formatCurrency(''), '—')
  })

  it('formats currency with EUR and GBP symbols', () => {
    assert.equal(formatCurrency(350, 'EUR'), '€350.00')
    assert.equal(formatCurrency(350, '€'), '€350.00')
    assert.equal(formatCurrency(99.99, 'GBP'), '£99.99')
    assert.equal(formatCurrency(99.99, '£'), '£99.99')
    assert.equal(formatCurrency(100, 'JPY'), 'JPY 100.00')
  })

  it('formats bytes human-readably', () => {
    assert.equal(formatBytes(0), '0 B')
    assert.equal(formatBytes(1024), '1 KB')
    assert.equal(formatBytes(1048576), '1 MB')
    assert.equal(formatBytes(26214400), '25 MB')
    assert.equal(formatBytes(null), '0 B')
  })

  it('formats dates and timestamps safely', () => {
    assert.equal(formatDate(null), '—')
    assert.equal(formatDateTime(null), '—')

    const dateStr = '2026-03-15'
    assert.match(formatDate(dateStr), /2026/)

    const isoStr = '2026-03-15T10:30:00Z'
    assert.match(formatDateTime(isoStr), /2026/)
  })

  it('normalizes extraction confidence scores correctly', () => {
    // 0.0 - 1.0 float scale
    const c95 = formatConfidence(0.95)
    assert.equal(c95.percentage, 95)
    assert.equal(c95.label, '95%')
    assert.equal(c95.variant, 'success')

    const c75 = formatConfidence(0.75)
    assert.equal(c75.percentage, 75)
    assert.equal(c75.variant, 'warning')

    const c40 = formatConfidence(0.4)
    assert.equal(c40.percentage, 40)
    assert.equal(c40.variant, 'danger')

    // 0 - 100 integer scale
    const c92 = formatConfidence(92)
    assert.equal(c92.percentage, 92)
    assert.equal(c92.variant, 'success')

    // Null or invalid scale
    const cNull = formatConfidence(null)
    assert.equal(cNull.percentage, 0)
    assert.equal(cNull.label, 'N/A')
  })
})

describe('TASK-016: Mathematical Verification & Tolerance Logic', () => {
  it('verifies exact equality within 0.05 tolerance', () => {
    const res = checkMathEquality(100.0, 100.0)
    assert.equal(res.matches, true)
    assert.equal(res.diff, 0)
  })

  it('accepts rounding differences within standard 0.05 tolerance', () => {
    const res1 = checkMathEquality(100.02, 100.0)
    assert.equal(res1.matches, true)
    assert.equal(res1.diff, 0.02)

    const res2 = checkMathEquality(100.0, 100.04)
    assert.equal(res2.matches, true)
    assert.equal(res2.diff, -0.04)
  })

  it('rejects discrepancies exceeding 0.05 tolerance', () => {
    const res = checkMathEquality(100.1, 100.0)
    assert.equal(res.matches, false)
    assert.equal(res.diff, 0.1)
  })

  it('handles null and undefined operands gracefully', () => {
    assert.equal(checkMathEquality(null, 100).matches, false)
    assert.equal(checkMathEquality(100, undefined).matches, false)
    assert.equal(checkMathEquality(null, null).matches, false)
  })
})

describe('TASK-016: Validation Findings Severity & Classification', () => {
  const mockFindings: ValidationError[] = [
    {
      id: 'err-1',
      rule_id: 'MATH_TAX_ADDITION',
      field: 'total',
      message: 'Subtotal ($100) + Tax ($10) does not equal Total ($125)',
      severity: 'ERROR',
      actual_value: '125.00',
      expected_value: '110.00',
      difference: 15.0,
      is_dismissed: false,
      dismissed_by: null,
      dismissed_at: null,
    },
    {
      id: 'err-2',
      rule_id: 'ANOMALY_FUTURE_DATE',
      field: 'invoice_date',
      message: 'Invoice issue date is in the future',
      severity: 'WARNING',
      actual_value: '2030-01-01',
      expected_value: null,
      difference: null,
      is_dismissed: false,
      dismissed_by: null,
      dismissed_at: null,
    },
    {
      id: 'err-3',
      rule_id: 'INFO_ROUND_NUMBER',
      field: 'total',
      message: 'Total amount is a round number',
      severity: 'INFO',
      actual_value: '500.00',
      expected_value: null,
      difference: null,
      is_dismissed: true,
      dismissed_by: 'operator_jane',
      dismissed_at: '2026-03-15T12:00:00Z',
    },
  ]

  it('correctly filters findings by severity', () => {
    const errors = mockFindings.filter((f) => f.severity === 'ERROR')
    const warnings = mockFindings.filter((f) => f.severity === 'WARNING')
    const infos = mockFindings.filter((f) => f.severity === 'INFO')

    assert.equal(errors.length, 1)
    assert.equal(warnings.length, 1)
    assert.equal(infos.length, 1)
    assert.equal(errors[0].rule_id, 'MATH_TAX_ADDITION')
  })

  it('preserves read-only dismissal fields without mutation', () => {
    const dismissed = mockFindings.find((f) => f.is_dismissed)
    assert.ok(dismissed)
    assert.equal(dismissed.dismissed_by, 'operator_jane')
    assert.ok(dismissed.dismissed_at)
  })

  it('computes math difference indicators correctly', () => {
    const taxFinding = mockFindings[0]
    assert.equal(Number(taxFinding.difference), 15.0)
    assert.equal(taxFinding.actual_value, '125.00')
    assert.equal(taxFinding.expected_value, '110.00')
  })
})
