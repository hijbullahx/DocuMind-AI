import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Check, Copy, Search, Sparkles, X } from 'lucide-react'
import { EmptyOrProcessingState } from './EmptyOrProcessingState'

export interface SourceDocumentPaneProps {
  rawText: string | null | undefined
  searchQuery: string
  onSearchChange: (query: string) => void
  activeEvidenceKey: string | null
  activeEvidenceQuote: string | null
  onClearEvidence: () => void
  className?: string
}

export const SourceDocumentPane: React.FC<SourceDocumentPaneProps> = ({
  rawText,
  searchQuery,
  onSearchChange,
  activeEvidenceKey,
  activeEvidenceQuote,
  onClearEvidence,
  className = '',
}) => {
  const [copied, setCopied] = useState(false)
  const evidenceRef = useRef<HTMLSpanElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)

  // Split lines
  const lines = useMemo(() => {
    if (!rawText) return []
    return rawText.split('\n')
  }, [rawText])

  // Count search matches
  const matchCount = useMemo(() => {
    if (!searchQuery.trim() || !rawText) return 0
    try {
      const escaped = searchQuery.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const regex = new RegExp(escaped, 'gi')
      const matches = rawText.match(regex)
      return matches ? matches.length : 0
    } catch {
      return 0
    }
  }, [rawText, searchQuery])

  // Check if active evidence exists in raw text
  const evidenceFound = useMemo(() => {
    if (!activeEvidenceQuote || !rawText) return false
    return rawText.toLowerCase().includes(activeEvidenceQuote.toLowerCase())
  }, [rawText, activeEvidenceQuote])

  // Smooth scroll to the evidence highlight whenever it changes
  useEffect(() => {
    if (evidenceFound && evidenceRef.current) {
      evidenceRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }
  }, [activeEvidenceQuote, evidenceFound])

  const handleCopy = async () => {
    if (!rawText) return
    try {
      await navigator.clipboard.writeText(rawText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  // Tokenize a line into normal, search, and evidence segments safely without dangerouslySetInnerHTML
  const renderHighlightedLine = (line: string, lineIndex: number) => {
    const searchTarget = searchQuery.trim()
    const evidenceTarget = activeEvidenceQuote ? activeEvidenceQuote.trim() : null

    if (!searchTarget && !evidenceTarget) {
      return <span>{line || ' '}</span>
    }

    // Build regex pattern capturing both targets if present
    const patterns: { type: 'evidence' | 'search'; regex: RegExp }[] = []
    if (evidenceTarget) {
      try {
        patterns.push({
          type: 'evidence',
          regex: new RegExp(evidenceTarget.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
        })
      } catch {
        // ignore invalid regex
      }
    }
    if (searchTarget) {
      try {
        patterns.push({
          type: 'search',
          regex: new RegExp(searchTarget.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
        })
      } catch {
        // ignore invalid regex
      }
    }

    // If line has no matches from any pattern, render directly
    const hasAnyMatch = patterns.some((p) => p.regex.test(line))
    if (!hasAnyMatch) {
      return <span>{line || ' '}</span>
    }

    // Reset lastIndex for regexes
    patterns.forEach((p) => {
      p.regex.lastIndex = 0
    })

    // Merge match intervals
    interface MatchRange {
      start: number
      end: number
      type: 'evidence' | 'search'
    }

    const ranges: MatchRange[] = []
    patterns.forEach((p) => {
      let m: RegExpExecArray | null
      while ((m = p.regex.exec(line)) !== null) {
        if (m[0].length === 0) break
        ranges.push({
          start: m.index,
          end: m.index + m[0].length,
          type: p.type,
        })
      }
    })

    // Sort by start index; evidence takes precedence if ranges overlap
    ranges.sort((a, b) => {
      if (a.start !== b.start) return a.start - b.start
      if (a.type === 'evidence') return -1
      return 1
    })

    // Flatten non-overlapping ranges
    const nonOverlapping: MatchRange[] = []
    let cursor = 0

    ranges.forEach((r) => {
      if (r.start >= cursor) {
        nonOverlapping.push(r)
        cursor = r.end
      }
    })

    const segments: React.ReactNode[] = []
    let lastIdx = 0

    nonOverlapping.forEach((range, segIdx) => {
      if (range.start > lastIdx) {
        segments.push(
          <span key={`text-${lineIndex}-${segIdx}`}>
            {line.substring(lastIdx, range.start)}
          </span>
        )
      }

      const matchText = line.substring(range.start, range.end)
      if (range.type === 'evidence') {
        segments.push(
          <span
            key={`ev-${lineIndex}-${segIdx}`}
            ref={segIdx === 0 ? evidenceRef : undefined}
            className="bg-blue-600/40 text-blue-100 ring-2 ring-blue-400/80 font-bold px-1 py-0.5 rounded shadow-sm inline-block"
            title={`Evidence Grounding for [${activeEvidenceKey || 'field'}]`}
          >
            {matchText}
          </span>
        )
      } else {
        segments.push(
          <span
            key={`srch-${lineIndex}-${segIdx}`}
            className="bg-amber-500/30 text-amber-200 ring-1 ring-amber-400/60 font-semibold px-0.5 rounded inline-block"
          >
            {matchText}
          </span>
        )
      }

      lastIdx = range.end
    })

    if (lastIdx < line.length) {
      segments.push(
        <span key={`tail-${lineIndex}`}>
          {line.substring(lastIdx)}
        </span>
      )
    }

    return <span>{segments}</span>
  }

  if (!rawText || rawText.trim() === '') {
    return (
      <div className={`flex flex-col h-full bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden ${className}`}>
        <EmptyOrProcessingState type="empty-text" />
      </div>
    )
  }

  return (
    <div className={`flex flex-col h-full bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden ${className}`}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-950/80 border-b border-slate-800 shrink-0">
        {/* Search input in raw text */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search in source text..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-8 pr-8 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Toolbar actions & stats */}
        <div className="flex items-center gap-2">
          {searchQuery && (
            <span className="text-[11px] font-mono px-2 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
              {matchCount} {matchCount === 1 ? 'match' : 'matches'}
            </span>
          )}

          {activeEvidenceQuote && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-blue-950/80 text-blue-300 border border-blue-800/80 text-[11px] font-mono">
              <Sparkles className="w-3 h-3 text-blue-400 shrink-0" />
              <span className="truncate max-w-[120px]" title={activeEvidenceQuote}>
                {evidenceFound ? 'Evidence highlighted' : 'Evidence not in OCR'}
              </span>
              <button
                type="button"
                onClick={onClearEvidence}
                className="hover:text-blue-100 ml-1 text-slate-400"
                title="Clear evidence highlight"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700/80"
            title="Copy source document text to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-300">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-400" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Line numbers and monospaced text body */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-4 font-mono text-xs text-slate-300 select-text bg-slate-950/40"
      >
        <div className="space-y-0.5">
          {lines.map((line, idx) => (
            <div
              key={idx}
              className="flex items-start hover:bg-slate-800/20 rounded transition-colors group"
            >
              {/* Line number gutter */}
              <span className="w-10 pr-3 text-right text-slate-600 select-none shrink-0 font-mono text-[11px] group-hover:text-slate-400">
                {idx + 1}
              </span>

              {/* Line content */}
              <div className="flex-1 whitespace-pre-wrap break-words leading-relaxed pl-2 border-l border-slate-800/60 group-hover:border-slate-700">
                {renderHighlightedLine(line, idx)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
