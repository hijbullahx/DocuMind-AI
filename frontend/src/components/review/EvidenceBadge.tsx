import React from 'react'
import { Quote, Search } from 'lucide-react'

export interface EvidenceBadgeProps {
  fieldKey: string
  evidenceQuote?: string | null
  isActive?: boolean
  onHighlight?: (key: string, quote: string | null) => void
  className?: string
}

export const EvidenceBadge: React.FC<EvidenceBadgeProps> = ({
  fieldKey,
  evidenceQuote,
  isActive = false,
  onHighlight,
  className = '',
}) => {
  if (!evidenceQuote || evidenceQuote.trim() === '') {
    return null
  }

  const trimmed = evidenceQuote.trim()

  return (
    <button
      type="button"
      onClick={() => onHighlight?.(fieldKey, trimmed)}
      title={`Grounding evidence: "${trimmed}" (Click to highlight in source text)`}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-mono transition-all select-none group border ${
        isActive
          ? 'bg-blue-500/20 text-blue-300 border-blue-400/80 ring-2 ring-blue-500/40 shadow-sm'
          : 'bg-slate-800/80 hover:bg-blue-950/60 text-slate-400 hover:text-blue-300 border-slate-700/80 hover:border-blue-600/60'
      } ${className}`}
    >
      {isActive ? (
        <Search className="w-3 h-3 text-blue-400 shrink-0" />
      ) : (
        <Quote className="w-3 h-3 text-slate-500 group-hover:text-blue-400 shrink-0" />
      )}
      <span className="truncate max-w-[120px] font-sans">
        {trimmed}
      </span>
    </button>
  )
}
