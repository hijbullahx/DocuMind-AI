import React from 'react'
import {
  FileText,
  Calendar,
  Building2,
  DollarSign,
  ArrowRight,
  Tag,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { formatBytes } from '@/utils/formatters'
import type { SearchMatchedField, SearchResultItem } from '@/types/search'

export interface SearchResultCardProps {
  item: SearchResultItem
  onSelectDocument: (id: string) => void
  className?: string
}

function getMatchedFieldBadgeColor(field: SearchMatchedField): string {
  switch (field) {
    case 'INVOICE_NUMBER':
      return 'bg-blue-950/80 text-blue-300 border-blue-800/60'
    case 'FILENAME':
      return 'bg-indigo-950/80 text-indigo-300 border-indigo-800/60'
    case 'SUPPLIER_NAME':
      return 'bg-emerald-950/80 text-emerald-300 border-emerald-800/60'
    case 'CUSTOMER_NAME':
      return 'bg-cyan-950/80 text-cyan-300 border-cyan-800/60'
    case 'LINE_ITEM':
      return 'bg-amber-950/80 text-amber-300 border-amber-800/60'
    case 'OCR_CONTENT':
      return 'bg-purple-950/80 text-purple-300 border-purple-800/60'
    default:
      return 'bg-slate-800 text-slate-300 border-slate-700'
  }
}

export const SearchResultCard: React.FC<SearchResultCardProps> = ({
  item,
  onSelectDocument,
  className = '',
}) => {
  const badgeClass = getMatchedFieldBadgeColor(item.matched_field)

  const formattedDate = item.created_at
    ? new Date(item.created_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null

  return (
    <div
      onClick={() => onSelectDocument(item.id)}
      className={`group p-4 bg-slate-900 border border-slate-800 hover:border-brand-500/50 rounded-2xl transition-all shadow-sm hover:shadow-md hover:shadow-brand-500/5 cursor-pointer space-y-3 ${className}`}
    >
      {/* Top Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-2 rounded-xl bg-slate-800 text-brand-400 group-hover:bg-brand-500/10 transition-colors shrink-0">
            <FileText className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-slate-100 group-hover:text-brand-300 transition-colors truncate">
              {item.filename}
            </h4>
            <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono mt-0.5">
              <span className="uppercase">{item.file_type}</span>
              <span>•</span>
              <span>{formatBytes(item.file_size_bytes)}</span>
              {formattedDate && (
                <>
                  <span>•</span>
                  <span>{formattedDate}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Matched Field Reason */}
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border font-mono uppercase tracking-wider ${badgeClass}`}
            title={`Matched in: ${item.matched_field_label}`}
          >
            <Tag className="w-3 h-3" />
            <span>{item.matched_field_label}</span>
          </span>

          <Badge variant={item.status} size="sm">
            {item.status}
          </Badge>
          <Badge variant={item.validation_status} size="sm">
            {item.validation_status}
          </Badge>
        </div>
      </div>

      {/* Structured Financial Details (if available) */}
      {(item.invoice_number || item.supplier_name || item.total) && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs font-mono">
          {item.invoice_number && (
            <div className="p-2 bg-slate-950/70 rounded-lg border border-slate-800/80">
              <span className="text-[10px] text-slate-500 uppercase block">Invoice #</span>
              <span className="text-slate-200 font-semibold truncate block">
                {item.invoice_number}
              </span>
            </div>
          )}

          {item.supplier_name && (
            <div className="p-2 bg-slate-950/70 rounded-lg border border-slate-800/80">
              <span className="text-[10px] text-slate-500 uppercase block flex items-center gap-1">
                <Building2 className="w-2.5 h-2.5" /> Supplier
              </span>
              <span className="text-slate-200 font-medium truncate block font-sans">
                {item.supplier_name}
              </span>
            </div>
          )}

          {item.invoice_date && (
            <div className="p-2 bg-slate-950/70 rounded-lg border border-slate-800/80">
              <span className="text-[10px] text-slate-500 uppercase block flex items-center gap-1">
                <Calendar className="w-2.5 h-2.5" /> Inv Date
              </span>
              <span className="text-slate-200 font-medium truncate block">
                {item.invoice_date}
              </span>
            </div>
          )}

          {item.total && (
            <div className="p-2 bg-slate-950/70 rounded-lg border border-slate-800/80">
              <span className="text-[10px] text-slate-500 uppercase block flex items-center gap-1">
                <DollarSign className="w-2.5 h-2.5" /> Total
              </span>
              <span className="text-emerald-300 font-bold truncate block">
                {item.currency || '$'}{Number(item.total).toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Snippet Container */}
      {item.snippet && (
        <div className="p-3 bg-slate-950/90 rounded-xl border border-slate-800/90 text-xs text-slate-300 font-mono leading-relaxed">
          <div
            dangerouslySetInnerHTML={{ __html: item.snippet }}
            className="line-clamp-2"
          />
        </div>
      )}

      {/* Action Footer */}
      <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-800/60">
        <span className="text-[11px] text-slate-500 font-sans">
          Click to inspect and verify in Review Workbench
        </span>

        <span className="flex items-center gap-1 text-brand-400 group-hover:text-brand-300 font-medium transition-colors">
          <span>Open Review</span>
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </div>
  )
}
