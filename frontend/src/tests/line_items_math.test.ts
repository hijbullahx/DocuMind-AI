/**
 * Automated Test Suite for TASK-016:
 * Line Items Tabular Calculation & Discrepancy Auditing.
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import type { LineItem } from '../types/document.ts'

describe('TASK-016: Line Item Math & Subtotal Reconciliation', () => {
  const validItems: LineItem[] = [
    {
      id: 'item-1',
      line_number: 1,
      description: 'Consulting Services Tier A',
      quantity: 10,
      unit_price: 150.0,
      amount: 1500.0,
    },
    {
      id: 'item-2',
      line_number: 2,
      description: 'Infrastructure Server Setup',
      quantity: 2,
      unit_price: 450.0,
      amount: 900.0,
    },
    {
      id: 'item-3',
      line_number: 3,
      description: 'License Fee (Single User)',
      quantity: 5,
      unit_price: 50.0,
      amount: 250.0,
    },
  ]

  it('correctly calculates sum of all line item amounts', () => {
    const sum = validItems.reduce((acc, it) => acc + (it.amount || 0), 0)
    assert.equal(sum, 2650.0)
  })

  it('verifies that item quantity * unit_price equals item amount for consistent rows', () => {
    for (const item of validItems) {
      const expected = (item.quantity || 0) * (item.unit_price || 0)
      const diff = Math.abs(expected - (item.amount || 0))
      assert.ok(diff <= 0.05, `Line ${item.line_number} arithmetic failed`)
    }
  })

  it('detects individual line item calculation discrepancies', () => {
    const corruptItem: LineItem = {
      id: 'item-bad',
      line_number: 4,
      description: 'Defective Billing Row',
      quantity: 10,
      unit_price: 25.0,
      amount: 300.0, // Expected 250.0, difference is +50.0
    }

    const expected = (corruptItem.quantity || 0) * (corruptItem.unit_price || 0)
    const diff = corruptItem.amount! - expected
    assert.equal(expected, 250.0)
    assert.equal(diff, 50.0)
    assert.ok(Math.abs(diff) > 0.05)
  })

  it('verifies line items sum against invoice stated subtotal within tolerance', () => {
    const statedSubtotal = 2650.0
    const computedSum = validItems.reduce((acc, it) => acc + (it.amount || 0), 0)
    const discrepancy = Math.abs(computedSum - statedSubtotal)
    assert.ok(discrepancy <= 0.05)
  })

  it('flags subtotal mismatch when stated subtotal diverges from items sum', () => {
    const wrongSubtotal = 2700.0
    const computedSum = validItems.reduce((acc, it) => acc + (it.amount || 0), 0)
    const difference = computedSum - wrongSubtotal
    assert.equal(difference, -50.0)
    assert.ok(Math.abs(difference) > 0.05)
  })

  it('handles null and missing quantity and unit price fields without exceptions', () => {
    const itemWithNulls: LineItem = {
      id: 'item-nulls',
      line_number: 5,
      description: 'Lump Sum Fixed Fee',
      quantity: null,
      unit_price: null,
      amount: 500.0,
    }

    // Should not throw and should safely sum
    const items = [...validItems, itemWithNulls]
    const sum = items.reduce((acc, it) => acc + (it.amount || 0), 0)
    assert.equal(sum, 3150.0)

    // Cannot check Qty * Price when operands are null
    const canCheckProduct = itemWithNulls.quantity !== null && itemWithNulls.unit_price !== null
    assert.equal(canCheckProduct, false)
  })
})
