/**
 * Financial Calculation & Reconciliation Engine for DocuMind-AI.
 * Enforces decimal-safe precision, rounding rules, and arithmetic tolerance.
 */

export const FINANCIAL_TOLERANCE = 0.05

export interface LineItemLike {
  quantity?: number | string | null
  unit_price?: number | string | null
  amount?: number | string | null
}

export interface InvoiceReconciliationResult {
  lineItemsSum: number
  isLineItemsSumBalanced: boolean
  lineItemsSumDiff: number

  calculatedTotal: number | null
  isTaxAdditionBalanced: boolean
  taxAdditionDiff: number

  isFullyBalanced: boolean
}

/**
 * Safely parses numeric string or number into float rounded to decimal places.
 * Uses exponential rounding to eliminate binary floating point inaccuracies (e.g. 1.005).
 */
export function safeRound(value: number | string | null | undefined, decimals = 2): number | null {
  if (value === null || value === undefined || value === '') return null
  const num = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''))
  if (isNaN(num)) return null
  return Number(Math.round(Number(num + 'e' + decimals)) + 'e-' + decimals)
}

/**
 * Calculates Amount = Quantity * Unit Price rounded to 2 decimal places.
 */
export function calculateLineItemAmount(
  quantity: number | string | null | undefined,
  unitPrice: number | string | null | undefined
): number | null {
  const q = safeRound(quantity, 4)
  const p = safeRound(unitPrice, 4)
  if (q === null || p === null) return null
  return safeRound(q * p, 2)
}

/**
 * Computes the sum of all line item amounts.
 * If amount is not provided, falls back to quantity * unit_price.
 */
export function calculateLineItemsSum(items: LineItemLike[]): number {
  if (!items || items.length === 0) return 0
  const totalCents = items.reduce((acc, item) => {
    let amt = safeRound(item.amount, 2)
    if (amt === null && item.quantity !== undefined && item.unit_price !== undefined) {
      amt = calculateLineItemAmount(item.quantity, item.unit_price)
    }
    return acc + (amt !== null ? Math.round(amt * 100) : 0)
  }, 0)
  return totalCents / 100
}

/**
 * Computes Subtotal + Tax = Total.
 */
export function calculateExpectedTotal(
  subtotal: number | string | null | undefined,
  tax: number | string | null | undefined
): number | null {
  const s = safeRound(subtotal, 2)
  const t = safeRound(tax, 2)
  if (s === null) return t
  if (t === null) return s
  return safeRound(s + t, 2)
}

/**
 * Reconciles invoice line items, subtotal, tax, and grand total within financial tolerance.
 */
export function reconcileInvoice(
  subtotal: number | string | null | undefined,
  tax: number | string | null | undefined,
  total: number | string | null | undefined,
  lineItems: LineItemLike[],
  tolerance = FINANCIAL_TOLERANCE
): InvoiceReconciliationResult {
  const lineItemsSum = calculateLineItemsSum(lineItems)
  const s = safeRound(subtotal, 2)
  const t = safeRound(tax, 2)
  const tot = safeRound(total, 2)

  // 1. Line items sum vs stated subtotal
  const lineItemsSumDiff = s !== null ? safeRound(lineItemsSum - s, 2) || 0 : 0
  const isLineItemsSumBalanced = s !== null ? Math.abs(lineItemsSumDiff) <= tolerance : true

  // 2. Subtotal + Tax vs Stated Total
  const calculatedTotal = calculateExpectedTotal(s, t)
  const taxAdditionDiff =
    calculatedTotal !== null && tot !== null
      ? safeRound(tot - calculatedTotal, 2) || 0
      : 0
  const isTaxAdditionBalanced =
    calculatedTotal !== null && tot !== null
      ? Math.abs(taxAdditionDiff) <= tolerance
      : true

  const isFullyBalanced = isLineItemsSumBalanced && isTaxAdditionBalanced

  return {
    lineItemsSum,
    isLineItemsSumBalanced,
    lineItemsSumDiff,
    calculatedTotal,
    isTaxAdditionBalanced,
    taxAdditionDiff,
    isFullyBalanced,
  }
}
