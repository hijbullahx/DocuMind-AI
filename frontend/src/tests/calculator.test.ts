/**
 * Automated Test Suite for TASK-017:
 * Financial Calculation Engine & Reconciliation (calculator.ts)
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  calculateExpectedTotal,
  calculateLineItemAmount,
  calculateLineItemsSum,
  reconcileInvoice,
  safeRound,
} from '../utils/calculator.ts'
import type { LineItemCorrectionPayload } from '../types/document.ts'

describe('TASK-017: Financial Calculator & Arithmetic Utility', () => {
  describe('safeRound', () => {
    it('accurately rounds floating point numbers without IEEE 754 precision artifacts', () => {
      assert.equal(safeRound(1.005, 2), 1.01)
      assert.equal(safeRound(10.1234, 2), 10.12)
      assert.equal(safeRound(10.125, 2), 10.13)
      assert.equal(safeRound(0.1 + 0.2, 2), 0.3)
    })

    it('handles null, undefined, and NaN gracefully', () => {
      assert.equal(safeRound(null, 2), null)
      assert.equal(safeRound(undefined, 2), null)
      assert.equal(safeRound(NaN, 2), null)
      assert.equal(safeRound('', 2), null)
    })
  })

  describe('calculateLineItemAmount', () => {
    it('computes quantity * unit price rounded to 2 decimal places', () => {
      assert.equal(calculateLineItemAmount(3, 14.99), 44.97)
      assert.equal(calculateLineItemAmount(1.5, 20.0), 30.0)
      assert.equal(calculateLineItemAmount(10, 0.05), 0.5)
    })

    it('returns null if quantity or unit price is null or invalid', () => {
      assert.equal(calculateLineItemAmount(null, 10.0), null)
      assert.equal(calculateLineItemAmount(5, null), null)
      assert.equal(calculateLineItemAmount(null, null), null)
    })
  })

  describe('calculateLineItemsSum', () => {
    it('sums all item amounts safely', () => {
      const items: LineItemCorrectionPayload[] = [
        { line_number: 1, description: 'Service A', quantity: 1, unit_price: 100.5, amount: 100.5 },
        { line_number: 2, description: 'Service B', quantity: 2, unit_price: 50.25, amount: 100.5 },
        { line_number: 3, description: 'Service C', quantity: 1, unit_price: 24.0, amount: 24.0 },
      ]
      assert.equal(calculateLineItemsSum(items), 225.0)
    })

    it('falls back to quantity * unit_price when amount is missing', () => {
      const items: LineItemCorrectionPayload[] = [
        { line_number: 1, description: 'Item A', quantity: 2, unit_price: 45.0, amount: null },
        { line_number: 2, description: 'Item B', quantity: 1, unit_price: 10.0, amount: 10.0 },
      ]
      assert.equal(calculateLineItemsSum(items), 100.0)
    })

    it('returns 0 for empty item list', () => {
      assert.equal(calculateLineItemsSum([]), 0)
    })
  })

  describe('calculateExpectedTotal', () => {
    it('computes subtotal + tax rounded to 2 decimal places', () => {
      assert.equal(calculateExpectedTotal(100.0, 15.0), 115.0)
      assert.equal(calculateExpectedTotal(1234.56, 123.45), 1358.01)
    })

    it('treats null tax as 0 when subtotal is present', () => {
      assert.equal(calculateExpectedTotal(250.0, null), 250.0)
    })

    it('returns tax if subtotal is missing', () => {
      assert.equal(calculateExpectedTotal(null, 25.0), 25.0)
    })
  })

  describe('reconcileInvoice', () => {
    it('identifies clean reconciliation within 0.05 tolerance', () => {
      const items: LineItemCorrectionPayload[] = [
        { line_number: 1, description: 'Item 1', quantity: 2, unit_price: 50.0, amount: 100.0 },
        { line_number: 2, description: 'Item 2', quantity: 1, unit_price: 25.0, amount: 25.0 },
      ]
      const result = reconcileInvoice(125.0, 12.5, 137.5, items)
      assert.equal(result.isLineItemsSumBalanced, true)
      assert.equal(result.isTaxAdditionBalanced, true)
      assert.equal(result.isFullyBalanced, true)
      assert.equal(result.lineItemsSumDiff, 0)
      assert.equal(result.taxAdditionDiff, 0)
    })

    it('flags subtotal discrepancy when line items sum does not match subtotal', () => {
      const items: LineItemCorrectionPayload[] = [
        { line_number: 1, description: 'Item 1', quantity: 1, unit_price: 100.0, amount: 100.0 },
      ]
      // Subtotal is stated as 150.0, but items sum to 100.0 -> diff is -50.0
      const result = reconcileInvoice(150.0, 15.0, 165.0, items)
      assert.equal(result.isLineItemsSumBalanced, false)
      assert.equal(result.isTaxAdditionBalanced, true)
      assert.equal(result.isFullyBalanced, false)
      assert.equal(result.lineItemsSumDiff, -50.0)
    })

    it('flags total discrepancy when subtotal + tax != total', () => {
      const items: LineItemCorrectionPayload[] = [
        { line_number: 1, description: 'Item 1', quantity: 1, unit_price: 100.0, amount: 100.0 },
      ]
      // Subtotal 100, Tax 10, stated total is 120 (expected 110)
      const result = reconcileInvoice(100.0, 10.0, 120.0, items)
      assert.equal(result.isLineItemsSumBalanced, true)
      assert.equal(result.isTaxAdditionBalanced, false)
      assert.equal(result.isFullyBalanced, false)
      assert.equal(result.taxAdditionDiff, 10.0)
    })
  })
})
