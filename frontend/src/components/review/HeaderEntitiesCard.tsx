import React from 'react'
import { Building2, Calendar, Hash, MapPin, User } from 'lucide-react'
import { EvidenceBadge } from './EvidenceBadge'
import { formatCurrency, formatDate } from '@/utils/formatters'
import type { InvoiceExtraction } from '@/types/document'

export interface HeaderEntitiesCardProps {
  extraction: InvoiceExtraction | null
  activeEvidenceKey: string | null
  onHighlightEvidence: (key: string, quote: string | null) => void
  className?: string
}

export const HeaderEntitiesCard: React.FC<HeaderEntitiesCardProps> = ({
  extraction,
  activeEvidenceKey,
  onHighlightEvidence,
  className = '',
}) => {
  if (!extraction) {
    return (
      <div className={`p-6 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800 ${className}`}>
        No structured extraction data available.
      </div>
    )
  }

  const evidence = (extraction.raw_text_evidence || {}) as Record<string, string>
  const currency = extraction.currency || 'USD'

  return (
    <div className={`space-y-5 ${className}`}>
      {/* Primary Financial Totals Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-950/70 border border-slate-800/90 shadow-sm">
        {/* Subtotal */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Subtotal
            </span>
            <EvidenceBadge
              fieldKey="subtotal"
              evidenceQuote={evidence.subtotal}
              isActive={activeEvidenceKey === 'subtotal'}
              onHighlight={onHighlightEvidence}
            />
          </div>
          <div className="text-base sm:text-lg font-mono font-bold text-slate-100">
            {formatCurrency(extraction.subtotal, currency)}
          </div>
        </div>

        {/* Tax */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Tax / VAT
            </span>
            <EvidenceBadge
              fieldKey="tax"
              evidenceQuote={evidence.tax}
              isActive={activeEvidenceKey === 'tax'}
              onHighlight={onHighlightEvidence}
            />
          </div>
          <div className="text-base sm:text-lg font-mono font-bold text-slate-100">
            {formatCurrency(extraction.tax, currency)}
          </div>
        </div>

        {/* Total Payable */}
        <div className="space-y-1 col-span-2 sm:col-span-1 border-t sm:border-t-0 sm:border-l border-slate-800 sm:pl-3 pt-2 sm:pt-0">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-semibold">
              Total Payable
            </span>
            <EvidenceBadge
              fieldKey="total"
              evidenceQuote={evidence.total}
              isActive={activeEvidenceKey === 'total'}
              onHighlight={onHighlightEvidence}
            />
          </div>
          <div className="text-lg sm:text-xl font-mono font-extrabold text-emerald-400">
            {formatCurrency(extraction.total, currency)}
          </div>
        </div>

        {/* Currency & Model */}
        <div className="space-y-1 col-span-2 sm:col-span-1 border-t sm:border-t-0 sm:border-l border-slate-800 sm:pl-3 pt-2 sm:pt-0">
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium block">
            Currency & Model
          </span>
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-200 font-mono text-xs font-semibold">
              {currency}
            </span>
            {extraction.llm_model && (
              <span className="px-1.5 py-0.5 rounded bg-blue-950/80 text-blue-300 border border-blue-800/60 text-[10px] font-mono">
                {extraction.llm_model}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Invoice Identifiers & Dates */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Invoice Number */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs">
              <Hash className="w-3.5 h-3.5 text-brand-400" />
              <span className="font-medium">Invoice Number</span>
            </div>
            <EvidenceBadge
              fieldKey="invoice_number"
              evidenceQuote={evidence.invoice_number}
              isActive={activeEvidenceKey === 'invoice_number'}
              onHighlight={onHighlightEvidence}
            />
          </div>
          <div className="font-mono text-sm font-semibold text-slate-100 truncate" title={extraction.invoice_number || '—'}>
            {extraction.invoice_number || '—'}
          </div>
        </div>

        {/* Issue Date */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs">
              <Calendar className="w-3.5 h-3.5 text-blue-400" />
              <span className="font-medium">Invoice Date</span>
            </div>
            <EvidenceBadge
              fieldKey="invoice_date"
              evidenceQuote={evidence.invoice_date}
              isActive={activeEvidenceKey === 'invoice_date'}
              onHighlight={onHighlightEvidence}
            />
          </div>
          <div className="font-mono text-sm text-slate-100">
            {formatDate(extraction.invoice_date)}
          </div>
        </div>

        {/* Due Date */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-slate-400 text-xs">
              <Calendar className="w-3.5 h-3.5 text-amber-400" />
              <span className="font-medium">Due Date</span>
            </div>
            <EvidenceBadge
              fieldKey="due_date"
              evidenceQuote={evidence.due_date}
              isActive={activeEvidenceKey === 'due_date'}
              onHighlight={onHighlightEvidence}
            />
          </div>
          <div className="font-mono text-sm text-slate-100">
            {formatDate(extraction.due_date)}
          </div>
        </div>
      </div>

      {/* Supplier and Customer Information */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Supplier / Vendor */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Building2 className="w-4 h-4 text-emerald-400" />
              <span>Supplier / Vendor</span>
            </div>
            <EvidenceBadge
              fieldKey="supplier_name"
              evidenceQuote={evidence.supplier_name}
              isActive={activeEvidenceKey === 'supplier_name'}
              onHighlight={onHighlightEvidence}
            />
          </div>

          <div className="space-y-1">
            <div className="text-sm font-semibold text-slate-100 leading-snug">
              {extraction.supplier_name || '—'}
            </div>
            <div className="text-xs text-slate-400 flex items-start gap-1 pt-1">
              <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
              <span className="leading-relaxed whitespace-pre-line">
                {extraction.supplier_address || 'No address specified'}
              </span>
            </div>
          </div>
        </div>

        {/* Customer / Bill-To */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <User className="w-4 h-4 text-brand-400" />
              <span>Customer / Bill-To</span>
            </div>
            <EvidenceBadge
              fieldKey="customer_name"
              evidenceQuote={evidence.customer_name}
              isActive={activeEvidenceKey === 'customer_name'}
              onHighlight={onHighlightEvidence}
            />
          </div>

          <div className="space-y-1">
            <div className="text-sm font-semibold text-slate-100 leading-snug">
              {extraction.customer_name || '—'}
            </div>
            <div className="text-xs text-slate-400 flex items-start gap-1 pt-1">
              <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
              <span className="leading-relaxed whitespace-pre-line">
                {extraction.customer_address || 'No address specified'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
