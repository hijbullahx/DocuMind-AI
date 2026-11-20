import React from 'react'
import { AlertCircle, CheckCircle2, FileQuestion, FileText, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export interface EmptyOrProcessingStateProps {
  type: 'no-selection' | 'queued' | 'processing' | 'failed' | 'empty-text' | 'no-items'
  title?: string
  description?: string
  errorMessage?: string | null
  onRefresh?: () => void
  onReprocess?: () => void
  isReprocessing?: boolean
  className?: string
}

export const EmptyOrProcessingState: React.FC<EmptyOrProcessingStateProps> = ({
  type,
  title,
  description,
  errorMessage,
  onRefresh,
  onReprocess,
  isReprocessing = false,
  className = '',
}) => {
  switch (type) {
    case 'no-selection':
      return (
        <div className={`flex flex-col items-center justify-center p-12 text-center text-slate-400 space-y-4 ${className}`}>
          <div className="w-16 h-16 rounded-2xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-center text-slate-400 shadow-inner">
            <FileText className="w-8 h-8" />
          </div>
          <div className="space-y-1.5 max-w-sm">
            <h3 className="text-base font-semibold text-slate-200">
              {title || 'No Document Selected'}
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              {description || 'Choose a document from the selector list to inspect its source text, extracted entities, and validation findings.'}
            </p>
          </div>
        </div>
      )

    case 'queued':
    case 'processing':
      return (
        <div className={`flex flex-col items-center justify-center p-12 text-center text-slate-400 space-y-4 ${className}`}>
          <div className="w-16 h-16 rounded-2xl bg-blue-950/60 border border-blue-800/60 flex items-center justify-center text-blue-400 shadow-inner">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
          <div className="space-y-1.5 max-w-md">
            <h3 className="text-base font-semibold text-slate-200">
              {title || (type === 'queued' ? 'Document Queued for Processing' : 'Extraction Pipeline in Progress')}
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              {description ||
                'The document is currently queued or undergoing OCR extraction, financial parsing, and deterministic mathematical validation. Results will appear once completed.'}
            </p>
          </div>
          {onRefresh && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRefresh}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh Status
            </Button>
          )}
        </div>
      )

    case 'failed':
      return (
        <div className={`flex flex-col items-center justify-center p-8 text-center text-rose-400 space-y-4 ${className}`}>
          <div className="w-16 h-16 rounded-2xl bg-rose-950/60 border border-rose-800/60 flex items-center justify-center text-rose-400 shadow-inner">
            <AlertCircle className="w-8 h-8" />
          </div>
          <div className="space-y-1.5 max-w-md">
            <h3 className="text-base font-semibold text-rose-200">
              {title || 'Document Processing Failed'}
            </h3>
            <p className="text-xs text-rose-300/80 leading-relaxed">
              {errorMessage || description || 'An error occurred during ingestion or extraction.'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {onRefresh && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRefresh}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Refresh
              </Button>
            )}
            {onReprocess && (
              <Button
                variant="destructive"
                size="sm"
                onClick={onReprocess}
                isLoading={isReprocessing}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry Processing
              </Button>
            )}
          </div>
        </div>
      )

    case 'empty-text':
      return (
        <div className={`flex flex-col items-center justify-center p-12 text-center text-slate-400 space-y-3 ${className}`}>
          <FileQuestion className="w-10 h-10 text-slate-500" />
          <div className="space-y-1 max-w-sm">
            <h4 className="text-sm font-medium text-slate-200">
              {title || 'No Extracted Text Available'}
            </h4>
            <p className="text-xs text-slate-500">
              {description || 'This document contains no raw OCR or digital text, or extraction is still in progress.'}
            </p>
          </div>
        </div>
      )

    case 'no-items':
      return (
        <div className={`flex flex-col items-center justify-center p-8 text-center text-slate-400 space-y-2 ${className}`}>
          <CheckCircle2 className="w-8 h-8 text-slate-600" />
          <h4 className="text-sm font-medium text-slate-300">
            {title || 'No Line Items Detected'}
          </h4>
          <p className="text-xs text-slate-500 max-w-sm">
            {description || 'This invoice extraction contains no itemized line items in the table structure.'}
          </p>
        </div>
      )

    default:
      return null
  }
}
