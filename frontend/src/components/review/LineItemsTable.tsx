import React from 'react'
import { AlertTriangle, Check, CheckCircle2, ListFilter, Table } from 'lucide-react'
import { formatCurrency } from '@/utils/formatters'
import type { LineItem } from '@/types/document'

export interface LineItemsTableProps {
  items: LineItem[]
  currency?: string | null
  statedSubtotal?: number | null
  className?: string
}

export const LineItemsTable: React.FC<LineItemsTableProps> = ({
  items,
  currency = 'USD',
  statedSubtotal = null,
  className = '',
}) => {
  if (!items || items.length === 0) {
    return (
      <div className={`p-8 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800 space-y-2 ${className}`}>
        <Table className="w-8 h-8 text-slate-600 mx-auto" />
        <h4 className="text-sm font-medium text-slate-300">No Itemized Line Items</h4>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          No structured line items were extracted for this invoice.
        </p>
      </div>
    )
  }

  // Calculate sum of line item amounts
  const computedSum = items.reduce((acc, item) => {
    const amt = typeof item.amount === 'number' ? item.amount : parseFloat(String(item.amount || 0))
    return acc + (isNaN(amt) ? 0 : amt)
  }, 0)

  // Verify against stated subtotal if provided
  const hasSubtotalMismatch =
    statedSubtotal !== null &&
    !isNaN(statedSubtotal) &&
    Math.abs(computedSum - statedSubtotal) > 0.05

  const subtotalDiff = statedSubtotal !== null ? Math.round((computedSum - statedSubtotal) * 100) / 100 : 0

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Table container */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 shadow-xs">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800/90 bg-slate-900/90 text-slate-400 uppercase tracking-wider text-[10px] font-semibold">
              <th className="py-2.5 px-3 w-10 text-center">#</th>
              <th className="py-2.5 px-3">Description</th>
              <th className="py-2.5 px-3 text-right w-20">Quantity</th>
              <th className="py-2.5 px-3 text-right w-28">Unit Price</th>
              <th className="py-2.5 px-3 text-right w-28">Amount</th>
              <th className="py-2.5 px-3 text-center w-36">Qty × Price Check</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {items.map((item, idx) => {
              const qty = item.quantity !== null ? Number(item.quantity) : null
              const price = item.unit_price !== null ? Number(item.unit_price) : null
              const amt = item.amount !== null ? Number(item.amount) : null

              const canCheckProduct = qty !== null && price !== null && amt !== null
              const expectedAmt = canCheckProduct ? Math.round(qty! * price! * 100) / 100 : null
              const productDiff = canCheckProduct ? Math.round((expectedAmt! - amt!) * 100) / 100 : null
              const hasProductMismatch = canCheckProduct && Math.abs(productDiff!) > 0.05

              return (
                <tr key={item.id || idx} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 px-3 text-center font-mono text-slate-500">
                    {item.line_number || idx + 1}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-slate-200">
                    {item.description || '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {item.quantity !== null ? item.quantity : '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {item.unit_price !== null ? formatCurrency(item.unit_price, currency) : '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-100">
                    {item.amount !== null ? formatCurrency(item.amount, currency) : '—'}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    {canCheckProduct ? (
                      hasProductMismatch ? (
                        <span
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-950/70 text-amber-300 border border-amber-800/60"
                          title={`Expected: ${formatCurrency(expectedAmt, currency)}, Actual: ${formatCurrency(amt, currency)}, Diff: ${productDiff}`}
                        >
                          <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>Diff: {productDiff}</span>
                        </span>
                      ) : (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-medium"
                          title="Quantity × Unit Price matches line amount"
                        >
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span>Exact</span>
                        </span>
                      )
                    ) : (
                      <span className="text-slate-600 font-mono text-[11px]">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Recalculation & Summary Footer */}
      <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <ListFilter className="w-4 h-4 text-slate-500" />
          <span>Total Itemized Lines: <strong className="text-slate-200">{items.length}</strong></span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Calculated Sum:</span>
            <span className="font-mono font-bold text-slate-100 text-sm">
              {formatCurrency(computedSum, currency)}
            </span>
          </div>

          {statedSubtotal !== null && (
            <div className="flex items-center gap-2 border-l border-slate-800 pl-4">
              <span className="text-slate-400">Stated Subtotal:</span>
              <span className="font-mono text-slate-200">
                {formatCurrency(statedSubtotal, currency)}
              </span>

              {hasSubtotalMismatch ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-rose-950/80 text-rose-300 border border-rose-800/80">
                  <AlertTriangle className="w-3 h-3 text-rose-400" />
                  <span>Mismatch ({subtotalDiff > 0 ? `+${subtotalDiff}` : subtotalDiff})</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px] font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Verified Match</span>
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
