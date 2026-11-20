import React, { type FormEvent, type KeyboardEvent } from 'react'
import { Search, X, Loader2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export interface SearchBarProps {
  value: string
  onChange: (val: string) => void
  onSearch: (query: string) => void
  onClear: () => void
  isLoading?: boolean
  className?: string
  placeholder?: string
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  onSearch,
  onClear,
  isLoading = false,
  className = '',
  placeholder = 'Search filenames, invoice #, suppliers, customers, line items, or OCR text...',
}) => {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSearch(value)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      onSearch(value)
    }
  }

  return (
    <form onSubmit={handleSubmit} className={`relative flex items-center gap-2 ${className}`}>
      <div className="relative flex-1">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
          <Search className="w-4 h-4" />
        </div>

        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-10 pr-10 py-3 bg-slate-900/90 border border-slate-800 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500/80 focus:ring-1 focus:ring-brand-500/40 shadow-sm transition-all"
        />

        {value && (
          <button
            type="button"
            onClick={onClear}
            className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300 transition-colors"
            title="Clear query"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <Button
        type="submit"
        variant="primary"
        disabled={isLoading || !value.trim()}
        className="px-5 py-3 h-auto text-xs font-semibold shrink-0 shadow-md shadow-brand-500/10"
      >
        {isLoading ? (
          <span className="flex items-center gap-1.5">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Searching...</span>
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            <Sparkles className="w-4 h-4" />
            <span>Search</span>
          </span>
        )}
      </Button>
    </form>
  )
}
