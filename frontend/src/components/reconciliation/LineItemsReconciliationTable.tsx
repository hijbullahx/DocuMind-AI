import React, { useMemo, useState } from 'react'
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  FileSpreadsheet,
  Filter,
} from 'lucide-react'
import type { LineItem } from '@/types/document'
import type { ReconciliationRecord } from '@/types/reconciliation'

export interface LineItemsReconciliationTableProps {
  record: ReconciliationRecord
  className?: string
}

type FilterMode = 'ALL' | 'DISCREPANCIES' | 'MATCHED'

interface PairedLineItemRow {
  key: string
  docAItem?: LineItem
  docBItem?: LineItem
  status: 'MATCH' | 'MISMATCH' | 'UNMATCHED_A' | 'UNMATCHED_B'
  qtyDiff?: number
  priceDiff?: number
  amountDiff?: number
  message?: string
}

function computeSimilarity(descA: string, descB: string): number {
  const normA = descA.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\s+/).filter(Boolean)
  const normB = descB.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(/\s+/).filter(Boolean)
  if (!normA.length || !normB.length) return 0
  const setA = new Set(normA)
  const setB = new Set(normB)
  const intersection = new Set([...setA].filter((x) => setB.has(x)))
  const union = new Set([...setA, ...setB])
  return intersection.size / union.size
}

export const LineItemsReconciliationTable: React.FC<LineItemsReconciliationTableProps> = ({
  record,
  className = '',
}) => {
  const [filterMode, setFilterMode] = useState<FilterMode>('ALL')

  // Deterministically match items from A and B
  const pairedRows = useMemo<PairedLineItemRow[]>(() => {
    const itemsA: LineItem[] = record.doc_a_details?.extraction?.line_items || []
    const itemsB: LineItem[] = record.doc_b_details?.extraction?.line_items || []
    const rows: PairedLineItemRow[] = []
    const matchedBIdxs = new Set<number>()

    // For each item in A, find best candidate in B
    itemsA.forEach((itA, idxA) => {
      let bestIdxB = -1
      let bestSim = 0

      itemsB.forEach((itB, idxB) => {
        if (matchedBIdxs.has(idxB)) return
        const sim = computeSimilarity(itA.description, itB.description)
        if (sim >= 0.4 && sim > bestSim) {
          bestSim = sim
          bestIdxB = idxB
        }
      })

      if (bestIdxB !== -1) {
        matchedBIdxs.add(bestIdxB)
        const itB = itemsB[bestIdxB]

        const qtyDiff =
          itA.quantity != null && itB.quantity != null
            ? Math.abs(Number(itA.quantity) - Number(itB.quantity))
            : undefined

        const priceDiff =
          itA.unit_price != null && itB.unit_price != null
            ? Math.abs(Number(itA.unit_price) - Number(itB.unit_price))
            : undefined

        const amtDiff =
          itA.amount != null && itB.amount != null
            ? Math.abs(Number(itA.amount) - Number(itB.amount))
            : undefined

        const hasDiscrepancy =
          (qtyDiff != null && qtyDiff > 0.001) ||
          (priceDiff != null && priceDiff > 0.05) ||
          (amtDiff != null && amtDiff > 0.05)

        rows.push({
          key: `pair-${idxA}-${bestIdxB}`,
          docAItem: itA,
          docBItem: itB,
          status: hasDiscrepancy ? 'MISMATCH' : 'MATCH',
          qtyDiff,
          priceDiff,
          amountDiff: amtDiff,
          message: hasDiscrepancy
            ? `Variance: ${amtDiff != null && amtDiff > 0.05 ? `Amt Diff: $${amtDiff.toFixed(2)}` : ''} ${qtyDiff != null && qtyDiff > 0.001 ? `Qty Diff: ${qtyDiff}` : ''}`
            : 'Line item matched across documents',
        })
      } else {
        rows.push({
          key: `unmatched-a-${idxA}`,
          docAItem: itA,
          status: 'UNMATCHED_A',
          message: 'Item present in Doc A but unmatched in Doc B',
        })
      }
    })

    // Add remaining unmatched items from B
    itemsB.forEach((itB, idxB) => {
      if (!matchedBIdxs.has(idxB)) {
        rows.push({
          key: `unmatched-b-${idxB}`,
          docBItem: itB,
          status: 'UNMATCHED_B',
          message: 'Item present in Doc B but unmatched in Doc A',
        })
      }
    })

    return rows
  }, [record])

  const filteredRows = useMemo(() => {
    if (filterMode === 'MATCHED') {
      return pairedRows.filter((r) => r.status === 'MATCH')
    }
    if (filterMode === 'DISCREPANCIES') {
      return pairedRows.filter((r) => r.status !== 'MATCH')
    }
    return pairedRows
  }, [pairedRows, filterMode])

  const docAName = record.doc_a_details?.filename || `Doc A (${record.doc_a.slice(0, 8)})`
  const docBName = record.doc_b_details?.filename || `Doc B (${record.doc_b.slice(0, 8)})`
  const itemsA = record.doc_a_details?.extraction?.line_items || []
  const itemsB = record.doc_b_details?.extraction?.line_items || []

  if (itemsA.length === 0 && itemsB.length === 0) {
    return (
      <div className={`bg-slate-900 border border-slate-800 rounded-xl p-8 text-center ${className}`}>
        <FileSpreadsheet className="w-10 h-10 text-slate-600 mx-auto mb-3" />
        <h4 className="text-sm font-semibold text-slate-300">No Tabular Line Items Found</h4>
        <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
          Neither document contains extracted line items, or both documents only contain summary financial totals.
        </p>
      </div>
    )
  }

  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg ${className}`}>
      {/* Header bar */}
      <div className="p-4 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4 bg-slate-900/60">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-brand-400" />
          <h3 className="text-sm font-bold text-slate-200">
            Line Items Cross-Reconciliation
          </h3>
          <span className="text-xs text-slate-500 ml-1">
            ({record.matched_items_count} matched, {record.unmatched_items_count} unmatched)
          </span>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
          <span className="flex items-center gap-1 text-slate-400 px-2">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </span>
          <button
            onClick={() => setFilterMode('ALL')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filterMode === 'ALL'
                ? 'bg-slate-800 text-brand-300'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({pairedRows.length})
          </button>
          <button
            onClick={() => setFilterMode('DISCREPANCIES')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filterMode === 'DISCREPANCIES'
                ? 'bg-amber-950/80 text-amber-300 border border-amber-800/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Discrepancies ({pairedRows.filter((r) => r.status !== 'MATCH').length})
          </button>
          <button
            onClick={() => setFilterMode('MATCHED')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filterMode === 'MATCHED'
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Matched ({pairedRows.filter((r) => r.status === 'MATCH').length})
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
              <th className="py-2.5 px-3 w-10 text-center">Status</th>
              <th className="py-2.5 px-3 min-w-[200px]">Doc A: {docAName}</th>
              <th className="py-2.5 px-3 w-16 text-right">Qty A</th>
              <th className="py-2.5 px-3 w-20 text-right">Unit A</th>
              <th className="py-2.5 px-3 w-24 text-right">Total A</th>
              <th className="py-2.5 px-3 min-w-[200px] border-l border-slate-800">Doc B: {docBName}</th>
              <th className="py-2.5 px-3 w-16 text-right">Qty B</th>
              <th className="py-2.5 px-3 w-20 text-right">Unit B</th>
              <th className="py-2.5 px-3 w-24 text-right">Total B</th>
              <th className="py-2.5 px-3 min-w-[140px]">Reconciliation Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {filteredRows.map((row) => {
              const isMatch = row.status === 'MATCH'
              const isMismatch = row.status === 'MISMATCH'
              const isUnmatchedA = row.status === 'UNMATCHED_A'
              const isUnmatchedB = row.status === 'UNMATCHED_B'

              return (
                <tr
                  key={row.key}
                  className={`transition-colors ${
                    isMatch
                      ? 'hover:bg-slate-800/30'
                      : isMismatch
                      ? 'bg-amber-950/15 hover:bg-amber-950/30'
                      : 'bg-rose-950/10 hover:bg-rose-950/20'
                  }`}
                >
                  {/* Status Indicator */}
                  <td className="py-3 px-3 text-center">
                    {isMatch && (
                      <span title="Line item matched">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                      </span>
                    )}
                    {isMismatch && (
                      <span title="Line item mismatch detected">
                        <AlertTriangle className="w-4 h-4 text-amber-400 inline" />
                      </span>
                    )}
                    {(isUnmatchedA || isUnmatchedB) && (
                      <span title="Unmatched line item">
                        <HelpCircle className="w-4 h-4 text-slate-500 inline" />
                      </span>
                    )}
                  </td>

                  {/* Doc A Line item details */}
                  <td className="py-3 px-3 font-sans text-slate-200">
                    {row.docAItem ? (
                      <span className="font-medium">{row.docAItem.description}</span>
                    ) : (
                      <span className="text-slate-600 italic font-mono text-[11px]">— No item in Doc A —</span>
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-300">
                    {row.docAItem?.quantity != null ? row.docAItem.quantity : '—'}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-300">
                    {row.docAItem?.unit_price != null
                      ? `$${Number(row.docAItem.unit_price).toFixed(2)}`
                      : '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-semibold text-slate-200">
                    {row.docAItem?.amount != null
                      ? `$${Number(row.docAItem.amount).toFixed(2)}`
                      : '—'}
                  </td>

                  {/* Doc B Line item details */}
                  <td className="py-3 px-3 font-sans text-slate-200 border-l border-slate-800">
                    {row.docBItem ? (
                      <span className="font-medium">{row.docBItem.description}</span>
                    ) : (
                      <span className="text-slate-600 italic font-mono text-[11px]">— No item in Doc B —</span>
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-300">
                    {row.docBItem?.quantity != null ? row.docBItem.quantity : '—'}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-300">
                    {row.docBItem?.unit_price != null
                      ? `$${Number(row.docBItem.unit_price).toFixed(2)}`
                      : '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-semibold text-slate-200">
                    {row.docBItem?.amount != null
                      ? `$${Number(row.docBItem.amount).toFixed(2)}`
                      : '—'}
                  </td>

                  {/* Notes & Variance */}
                  <td className="py-3 px-3 font-sans">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                        isMatch
                          ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/40'
                          : isMismatch
                          ? 'bg-amber-950/70 text-amber-300 border border-amber-800/40 font-medium'
                          : 'bg-slate-800/80 text-slate-400'
                      }`}
                    >
                      {row.message}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
