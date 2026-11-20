import React from 'react'
import {
  AlertTriangle,
  Calculator,
  Check,
  CheckCircle2,
  ListFilter,
  Plus,
  Table,
  Trash2,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatCurrency } from '@/utils/formatters'
import { calculateLineItemAmount } from '@/utils/calculator'
import type { LineItem, LineItemCorrectionPayload } from '@/types/document'

export interface LineItemsTableProps {
  items: LineItem[]
  currency?: string | null
  statedSubtotal?: number | null
  isEditMode?: boolean
  draftItems?: LineItemCorrectionPayload[]
  onUpdateItem?: (index: number, updatedItem: Partial<LineItemCorrectionPayload>) => void
  onAddItem?: () => void
  onRemoveItem?: (index: number) => void
  onApplyCalculatedSubtotal?: () => void
  className?: string
}

export const LineItemsTable: React.FC<LineItemsTableProps> = ({
  items,
  currency = 'USD',
  statedSubtotal = null,
  isEditMode = false,
  draftItems = [],
  onUpdateItem,
  onAddItem,
  onRemoveItem,
  onApplyCalculatedSubtotal,
  className = '',
}) => {
  // If editing, use draftItems; otherwise use extracted items
  const activeItems = isEditMode ? draftItems : items
  const effectiveCurrency = currency || 'USD'

  // Calculate sum of line item amounts
  const computedSum = activeItems.reduce((acc, item) => {
    const amt = typeof item.amount === 'number' ? item.amount : parseFloat(String(item.amount || 0))
    return acc + (isNaN(amt) ? 0 : amt)
  }, 0)

  const roundedSum = Math.round(computedSum * 100) / 100

  // Verify against stated subtotal if provided
  const hasSubtotalMismatch =
    statedSubtotal !== null &&
    !isNaN(statedSubtotal) &&
    Math.abs(roundedSum - statedSubtotal) > 0.05

  const subtotalDiff = statedSubtotal !== null ? Math.round((roundedSum - statedSubtotal) * 100) / 100 : 0

  if (!isEditMode && (!activeItems || activeItems.length === 0)) {
    return (
      <div className={`p-8 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800 space-y-2 ${className}`}>
        <Table className="w-8 h-8 text-slate-600 mx-auto" />
        <h4 className="text-sm font-medium text-slate-300">No Itemized Line Items</h4>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          No structured line items were extracted for this invoice. You can switch to Edit Mode to manually add itemized lines.
        </p>
      </div>
    )
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Table container */}
      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 shadow-xs">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800/90 bg-slate-900/90 text-slate-400 uppercase tracking-wider text-[10px] font-semibold">
              <th className="py-2.5 px-3 w-10 text-center">#</th>
              <th className="py-2.5 px-3 min-w-[180px]">Description</th>
              <th className="py-2.5 px-3 text-right w-24">Quantity</th>
              <th className="py-2.5 px-3 text-right w-28">Unit Price</th>
              <th className="py-2.5 px-3 text-right w-28">Amount</th>
              <th className="py-2.5 px-3 text-center w-36">
                {isEditMode ? 'Check / Actions' : 'Qty × Price Check'}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {activeItems.length === 0 && isEditMode && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500 italic">
                  No line items currently in draft. Click "Add Line Item" below to add an entry.
                </td>
              </tr>
            )}

            {activeItems.map((item, idx) => {
              const qty = item.quantity !== null && item.quantity !== undefined ? Number(item.quantity) : null
              const price = item.unit_price !== null && item.unit_price !== undefined ? Number(item.unit_price) : null
              const amt = item.amount !== null && item.amount !== undefined ? Number(item.amount) : null

              const canCheckProduct = qty !== null && price !== null && amt !== null
              const expectedAmt = canCheckProduct ? Math.round(qty! * price! * 100) / 100 : null
              const productDiff = canCheckProduct ? Math.round((expectedAmt! - amt!) * 100) / 100 : null
              const hasProductMismatch = canCheckProduct && Math.abs(productDiff!) > 0.05

              if (isEditMode && onUpdateItem) {
                return (
                  <tr key={item.id || `draft-line-${idx}`} className="bg-slate-900/30 hover:bg-slate-800/40 transition-colors">
                    <td className="py-2 px-3 text-center font-mono text-slate-400 font-semibold">
                      {idx + 1}
                    </td>
                    <td className="py-2 px-2">
                      <input
                        type="text"
                        aria-label={`Line ${idx + 1} Description`}
                        value={item.description || ''}
                        onChange={(e) => onUpdateItem(idx, { description: e.target.value })}
                        placeholder="Item description..."
                        className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                      />
                    </td>
                    <td className="py-2 px-2 text-right">
                      <input
                        type="number"
                        step="any"
                        aria-label={`Line ${idx + 1} Quantity`}
                        value={qty !== null ? qty : ''}
                        onChange={(e) => {
                          const val = e.target.value === '' ? null : Number(e.target.value)
                          const nextAmt = val !== null && price !== null ? calculateLineItemAmount(val, price) : amt
                          onUpdateItem(idx, { quantity: val, amount: nextAmt })
                        }}
                        placeholder="Qty"
                        className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-right font-mono text-slate-100 focus:outline-none focus:border-brand-500"
                      />
                    </td>
                    <td className="py-2 px-2 text-right">
                      <input
                        type="number"
                        step="0.01"
                        aria-label={`Line ${idx + 1} Unit Price`}
                        value={price !== null ? price : ''}
                        onChange={(e) => {
                          const val = e.target.value === '' ? null : Number(e.target.value)
                          const nextAmt = qty !== null && val !== null ? calculateLineItemAmount(qty, val) : amt
                          onUpdateItem(idx, { unit_price: val, amount: nextAmt })
                        }}
                        placeholder="0.00"
                        className="w-24 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-right font-mono text-slate-100 focus:outline-none focus:border-brand-500"
                      />
                    </td>
                    <td className="py-2 px-2 text-right">
                      <input
                        type="number"
                        step="0.01"
                        aria-label={`Line ${idx + 1} Amount`}
                        value={amt !== null ? amt : ''}
                        onChange={(e) => {
                          const val = e.target.value === '' ? null : Number(e.target.value)
                          onUpdateItem(idx, { amount: val })
                        }}
                        placeholder="0.00"
                        className="w-24 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-right font-mono font-bold text-slate-100 focus:outline-none focus:border-brand-500"
                      />
                    </td>
                    <td className="py-2 px-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        {canCheckProduct && (
                          <span
                            className={`inline-flex items-center gap-1 text-[10px] font-mono px-1 py-0.5 rounded ${
                              hasProductMismatch
                                ? 'bg-amber-950/70 text-amber-300 border border-amber-800/60'
                                : 'text-emerald-400'
                            }`}
                            title={
                              hasProductMismatch
                                ? `Mismatch: Qty (${qty}) × Price (${price}) = ${expectedAmt}, but amount is ${amt}`
                                : 'Valid product'
                            }
                          >
                            {hasProductMismatch ? (
                              <>
                                <AlertTriangle className="w-3 h-3 text-amber-400" />
                                <span>Diff: {productDiff}</span>
                              </>
                            ) : (
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                            )}
                          </span>
                        )}
                        {onRemoveItem && (
                          <button
                            type="button"
                            onClick={() => onRemoveItem(idx)}
                            className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                            title={`Delete line item ${idx + 1}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              }

              // Read-only mode rendering
              return (
                <tr key={item.id || idx} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 px-3 text-center font-mono text-slate-500">
                    {item.line_number || idx + 1}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-slate-200">
                    {item.description || '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {item.quantity !== null && item.quantity !== undefined ? item.quantity : '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {item.unit_price !== null && item.unit_price !== undefined
                      ? formatCurrency(item.unit_price, effectiveCurrency)
                      : '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-100">
                    {item.amount !== null && item.amount !== undefined
                      ? formatCurrency(item.amount, effectiveCurrency)
                      : '—'}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    {canCheckProduct ? (
                      hasProductMismatch ? (
                        <span
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-950/70 text-amber-300 border border-amber-800/60"
                          title={`Expected: ${formatCurrency(expectedAmt, effectiveCurrency)}, Actual: ${formatCurrency(amt, effectiveCurrency)}, Diff: ${productDiff}`}
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
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-slate-400">
            <ListFilter className="w-4 h-4 text-slate-500" />
            <span>Total Itemized Lines: <strong className="text-slate-200">{activeItems.length}</strong></span>
          </div>

          {isEditMode && onAddItem && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onAddItem}
              className="text-xs px-2.5 py-1 text-slate-200 border-slate-700 hover:border-brand-500 hover:text-white"
              leftIcon={<Plus className="w-3.5 h-3.5 text-brand-400" />}
            >
              Add Line Item
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Calculated Sum:</span>
            <span className="font-mono font-bold text-slate-100 text-sm">
              {formatCurrency(roundedSum, effectiveCurrency)}
            </span>
          </div>

          {/* One-click button to set draft subtotal to sum of items in edit mode */}
          {isEditMode && onApplyCalculatedSubtotal && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onApplyCalculatedSubtotal}
              className="text-xs px-2 py-1 text-brand-400 hover:text-brand-300 hover:bg-brand-950/40 border border-brand-800/60"
              leftIcon={<Calculator className="w-3 h-3" />}
              title="Set the Subtotal field to match this calculated sum of line items"
            >
              Set Subtotal from Items
            </Button>
          )}

          {statedSubtotal !== null && (
            <div className="flex items-center gap-2 border-l border-slate-800 pl-3">
              <span className="text-slate-400">Stated Subtotal:</span>
              <span className="font-mono text-slate-200">
                {formatCurrency(statedSubtotal, effectiveCurrency)}
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
