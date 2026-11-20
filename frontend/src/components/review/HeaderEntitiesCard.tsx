import React from 'react'
import {
  Building2,
  Calculator,
  Calendar,
  Edit2,
  Hash,
  MapPin,
  User,
} from 'lucide-react'
import { EvidenceBadge } from './EvidenceBadge'
import { Button } from '@/components/ui/Button'
import { formatCurrency, formatDate } from '@/utils/formatters'
import type { EditableExtractionDraft } from '@/hooks/useDocumentReview'
import type { DocumentDetail, InvoiceExtraction, ManualCorrectionsMetadata } from '@/types/document'

export interface HeaderEntitiesCardProps {
  document: DocumentDetail
  isEditMode?: boolean
  draft?: EditableExtractionDraft
  onUpdateDraftField?: (
    field: keyof Omit<EditableExtractionDraft, 'line_items'>,
    value: string | number | null
  ) => void
  onAutoCalculateTotal?: () => void
  activeEvidenceKey: string | null
  onHighlightEvidence: (key: string, quote: string | null) => void
  className?: string
}

export const HeaderEntitiesCard: React.FC<HeaderEntitiesCardProps> = ({
  document,
  isEditMode = false,
  draft,
  onUpdateDraftField,
  onAutoCalculateTotal,
  activeEvidenceKey,
  onHighlightEvidence,
  className = '',
}) => {
  const extraction: InvoiceExtraction | null = document.extraction

  if (!extraction && !isEditMode) {
    return (
      <div className={`p-6 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800 ${className}`}>
        No structured extraction data available.
      </div>
    )
  }

  const evidence = (extraction?.raw_text_evidence || {}) as Record<string, string>
  const manualCorrections = (document.metadata?.manual_corrections || null) as ManualCorrectionsMetadata | null
  const correctedFields = manualCorrections?.corrected_fields || []
  const originalExt = manualCorrections?.original_extraction || {}

  const currency = isEditMode && draft ? draft.currency : (extraction?.currency || 'USD')

  // Helper for rendering an "Edited" badge and original value in read-only mode
  const renderOriginalDiff = (fieldName: string, isCurrency = false) => {
    if (isEditMode || !correctedFields.includes(fieldName)) return null
    const origVal = originalExt[fieldName]
    if (origVal === undefined || origVal === null) return null

    const formattedOrig = isCurrency
      ? formatCurrency(origVal as unknown as number, currency)
      : String(origVal || '—')

    return (
      <div className="flex items-center gap-1.5 mt-1 text-[11px] font-mono text-amber-300/90 bg-amber-950/40 border border-amber-900/50 px-2 py-0.5 rounded">
        <span className="text-[10px] uppercase font-semibold text-amber-400">Orig (AI):</span>
        <span className="line-through text-slate-400">{formattedOrig}</span>
      </div>
    )
  }

  // Helper for field edited badge
  const renderEditedBadge = (fieldName: string) => {
    if (isEditMode || !correctedFields.includes(fieldName)) return null
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/70">
        <Edit2 className="w-2.5 h-2.5" />
        <span>Edited</span>
      </span>
    )
  }

  return (
    <div className={`space-y-5 ${className}`}>
      {/* Primary Financial Totals Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-950/70 border border-slate-800/90 shadow-sm">
        {/* Subtotal */}
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-1">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Subtotal
            </span>
            <div className="flex items-center gap-1">
              {renderEditedBadge('subtotal')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="subtotal"
                  evidenceQuote={evidence.subtotal}
                  isActive={activeEvidenceKey === 'subtotal'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <div className="space-y-1">
              <input
                type="number"
                step="0.01"
                aria-label="Invoice Subtotal"
                value={draft.subtotal !== null ? draft.subtotal : ''}
                onChange={(e) =>
                  onUpdateDraftField(
                    'subtotal',
                    e.target.value === '' ? null : Number(e.target.value)
                  )
                }
                placeholder="0.00"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-sm font-mono font-bold text-slate-100 focus:outline-none focus:border-brand-500"
              />
            </div>
          ) : (
            <>
              <div className="text-base sm:text-lg font-mono font-bold text-slate-100">
                {formatCurrency(extraction?.subtotal, currency)}
              </div>
              {renderOriginalDiff('subtotal', true)}
            </>
          )}
        </div>

        {/* Tax */}
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-1">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Tax / VAT
            </span>
            <div className="flex items-center gap-1">
              {renderEditedBadge('tax')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="tax"
                  evidenceQuote={evidence.tax}
                  isActive={activeEvidenceKey === 'tax'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <div className="space-y-1">
              <input
                type="number"
                step="0.01"
                aria-label="Invoice Tax"
                value={draft.tax !== null ? draft.tax : ''}
                onChange={(e) =>
                  onUpdateDraftField(
                    'tax',
                    e.target.value === '' ? null : Number(e.target.value)
                  )
                }
                placeholder="0.00"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-sm font-mono font-bold text-slate-100 focus:outline-none focus:border-brand-500"
              />
            </div>
          ) : (
            <>
              <div className="text-base sm:text-lg font-mono font-bold text-slate-100">
                {formatCurrency(extraction?.tax, currency)}
              </div>
              {renderOriginalDiff('tax', true)}
            </>
          )}
        </div>

        {/* Total Payable */}
        <div className="space-y-1 col-span-2 sm:col-span-1 border-t sm:border-t-0 sm:border-l border-slate-800 sm:pl-3 pt-2 sm:pt-0">
          <div className="flex items-center justify-between gap-1">
            <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-semibold">
              Total Payable
            </span>
            <div className="flex items-center gap-1">
              {renderEditedBadge('total')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="total"
                  evidenceQuote={evidence.total}
                  isActive={activeEvidenceKey === 'total'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <div className="space-y-1.5">
              <input
                type="number"
                step="0.01"
                aria-label="Invoice Total Payable"
                value={draft.total !== null ? draft.total : ''}
                onChange={(e) =>
                  onUpdateDraftField(
                    'total',
                    e.target.value === '' ? null : Number(e.target.value)
                  )
                }
                placeholder="0.00"
                className="w-full bg-slate-900 border border-emerald-500/50 rounded-lg px-2.5 py-1.5 text-sm font-mono font-bold text-emerald-400 focus:outline-none focus:border-emerald-400"
              />
              {onAutoCalculateTotal && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onAutoCalculateTotal}
                  className="w-full text-[10px] py-1 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/40 border border-emerald-900/50"
                  leftIcon={<Calculator className="w-3 h-3" />}
                  title="Auto-calculate Total as Subtotal + Tax"
                >
                  Calc Total (Subtotal + Tax)
                </Button>
              )}
            </div>
          ) : (
            <>
              <div className="text-lg sm:text-xl font-mono font-extrabold text-emerald-400">
                {formatCurrency(extraction?.total, currency)}
              </div>
              {renderOriginalDiff('total', true)}
            </>
          )}
        </div>

        {/* Currency & Model */}
        <div className="space-y-1 col-span-2 sm:col-span-1 border-t sm:border-t-0 sm:border-l border-slate-800 sm:pl-3 pt-2 sm:pt-0">
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium block">
            Currency & Metadata
          </span>

          {isEditMode && draft && onUpdateDraftField ? (
            <div className="space-y-1">
              <input
                type="text"
                maxLength={4}
                aria-label="Currency Code"
                value={draft.currency}
                onChange={(e) => onUpdateDraftField('currency', e.target.value.toUpperCase())}
                placeholder="USD"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono font-bold text-slate-100 uppercase focus:outline-none focus:border-brand-500"
              />
            </div>
          ) : (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-200 font-mono text-xs font-semibold">
                {currency}
              </span>
              {renderEditedBadge('currency')}
              {extraction?.llm_model && (
                <span className="px-1.5 py-0.5 rounded bg-blue-950/80 text-blue-300 border border-blue-800/60 text-[10px] font-mono">
                  {extraction.llm_model}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Invoice Identifiers & Dates */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Invoice Number */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between gap-1">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs">
              <Hash className="w-3.5 h-3.5 text-brand-400" />
              <span className="font-medium">Invoice Number</span>
            </div>
            <div className="flex items-center gap-1">
              {renderEditedBadge('invoice_number')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="invoice_number"
                  evidenceQuote={evidence.invoice_number}
                  isActive={activeEvidenceKey === 'invoice_number'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <input
              type="text"
              aria-label="Invoice Number"
              value={draft.invoice_number}
              onChange={(e) => onUpdateDraftField('invoice_number', e.target.value)}
              placeholder="e.g. INV-2024-001"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500"
            />
          ) : (
            <>
              <div className="font-mono text-sm font-semibold text-slate-100 truncate" title={extraction?.invoice_number || '—'}>
                {extraction?.invoice_number || '—'}
              </div>
              {renderOriginalDiff('invoice_number')}
            </>
          )}
        </div>

        {/* Issue Date */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between gap-1">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs">
              <Calendar className="w-3.5 h-3.5 text-blue-400" />
              <span className="font-medium">Invoice Date</span>
            </div>
            <div className="flex items-center gap-1">
              {renderEditedBadge('invoice_date')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="invoice_date"
                  evidenceQuote={evidence.invoice_date}
                  isActive={activeEvidenceKey === 'invoice_date'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <input
              type="date"
              aria-label="Invoice Issue Date"
              value={draft.invoice_date}
              onChange={(e) => onUpdateDraftField('invoice_date', e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500"
            />
          ) : (
            <>
              <div className="font-mono text-sm text-slate-100">
                {formatDate(extraction?.invoice_date)}
              </div>
              {renderOriginalDiff('invoice_date')}
            </>
          )}
        </div>

        {/* Due Date */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between gap-1">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs">
              <Calendar className="w-3.5 h-3.5 text-amber-400" />
              <span className="font-medium">Due Date</span>
            </div>
            <div className="flex items-center gap-1">
              {renderEditedBadge('due_date')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="due_date"
                  evidenceQuote={evidence.due_date}
                  isActive={activeEvidenceKey === 'due_date'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <input
              type="date"
              aria-label="Invoice Due Date"
              value={draft.due_date}
              onChange={(e) => onUpdateDraftField('due_date', e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-brand-500"
            />
          ) : (
            <>
              <div className="font-mono text-sm text-slate-100">
                {formatDate(extraction?.due_date)}
              </div>
              {renderOriginalDiff('due_date')}
            </>
          )}
        </div>
      </div>

      {/* Supplier and Customer Information */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Supplier / Vendor */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between gap-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Building2 className="w-4 h-4 text-emerald-400" />
              <span>Supplier / Vendor</span>
            </div>
            <div className="flex items-center gap-1">
              {renderEditedBadge('supplier_name')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="supplier_name"
                  evidenceQuote={evidence.supplier_name}
                  isActive={activeEvidenceKey === 'supplier_name'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <div className="space-y-2">
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-medium block mb-1">
                  Supplier Name
                </label>
                <input
                  type="text"
                  aria-label="Supplier Name"
                  value={draft.supplier_name}
                  onChange={(e) => onUpdateDraftField('supplier_name', e.target.value)}
                  placeholder="Supplier / Company Name"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-medium block mb-1">
                  Supplier Address
                </label>
                <textarea
                  rows={2}
                  aria-label="Supplier Address"
                  value={draft.supplier_address}
                  onChange={(e) => onUpdateDraftField('supplier_address', e.target.value)}
                  placeholder="Supplier Address..."
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-100 leading-snug">
                {extraction?.supplier_name || '—'}
              </div>
              {renderOriginalDiff('supplier_name')}
              <div className="text-xs text-slate-400 flex items-start gap-1 pt-1">
                <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
                <span className="leading-relaxed whitespace-pre-line">
                  {extraction?.supplier_address || 'No address specified'}
                </span>
              </div>
              {renderOriginalDiff('supplier_address')}
            </div>
          )}
        </div>

        {/* Customer / Bill-To */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between gap-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <User className="w-4 h-4 text-brand-400" />
              <span>Customer / Bill-To</span>
            </div>
            <div className="flex items-center gap-1">
              {renderEditedBadge('customer_name')}
              {!isEditMode && (
                <EvidenceBadge
                  fieldKey="customer_name"
                  evidenceQuote={evidence.customer_name}
                  isActive={activeEvidenceKey === 'customer_name'}
                  onHighlight={onHighlightEvidence}
                />
              )}
            </div>
          </div>

          {isEditMode && draft && onUpdateDraftField ? (
            <div className="space-y-2">
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-medium block mb-1">
                  Customer Name
                </label>
                <input
                  type="text"
                  aria-label="Customer Name"
                  value={draft.customer_name}
                  onChange={(e) => onUpdateDraftField('customer_name', e.target.value)}
                  placeholder="Customer / Client Name"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-medium block mb-1">
                  Customer Address
                </label>
                <textarea
                  rows={2}
                  aria-label="Customer Address"
                  value={draft.customer_address}
                  onChange={(e) => onUpdateDraftField('customer_address', e.target.value)}
                  placeholder="Customer Address..."
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-100 leading-snug">
                {extraction?.customer_name || '—'}
              </div>
              {renderOriginalDiff('customer_name')}
              <div className="text-xs text-slate-400 flex items-start gap-1 pt-1">
                <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
                <span className="leading-relaxed whitespace-pre-line">
                  {extraction?.customer_address || 'No address specified'}
                </span>
              </div>
              {renderOriginalDiff('customer_address')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
