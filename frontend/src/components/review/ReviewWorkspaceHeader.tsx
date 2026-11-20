import React, { useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  Columns,
  Edit3,
  FileText,
  Layout,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  RotateCcw,
  Save,
  Sparkles,
  Undo2,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatBytes, formatConfidence } from '@/utils/formatters'
import type { DocumentDetail } from '@/types/document'

export type PaneLayoutMode = 'split' | 'source-focus' | 'data-focus'

export interface ReviewWorkspaceHeaderProps {
  document: DocumentDetail | null
  isSelectorOpen: boolean
  onToggleSelector: () => void
  layoutMode: PaneLayoutMode
  onChangeLayoutMode: (mode: PaneLayoutMode) => void
  onRefresh: () => void
  onReprocess: (force?: boolean) => Promise<boolean>
  isReprocessing: boolean
  reprocessMessage: string | null
  reprocessError: string | null

  // TASK-017: Edit & Correction Actions
  isEditMode?: boolean
  onToggleEditMode?: () => void
  isDirty?: boolean
  dirtyFieldCount?: number
  isSavingCorrection?: boolean
  correctionSuccessMessage?: string | null
  correctionError?: string | null
  onSaveCorrections?: (operator?: string) => Promise<boolean>
  onCancelEditing?: () => void

  onNavigateBack?: () => void
  className?: string
}

export const ReviewWorkspaceHeader: React.FC<ReviewWorkspaceHeaderProps> = ({
  document,
  isSelectorOpen,
  onToggleSelector,
  layoutMode,
  onChangeLayoutMode,
  onRefresh,
  onReprocess,
  isReprocessing,
  reprocessMessage,
  reprocessError,
  isEditMode = false,
  onToggleEditMode,
  isDirty = false,
  dirtyFieldCount = 0,
  isSavingCorrection = false,
  correctionSuccessMessage = null,
  correctionError = null,
  onSaveCorrections,
  onCancelEditing,
  onNavigateBack,
  className = '',
}) => {
  const [showConfirmReprocess, setShowConfirmReprocess] = useState(false)
  const [showSavePrompt, setShowSavePrompt] = useState(false)
  const [operatorReason, setOperatorReason] = useState('')

  if (!document) {
    return (
      <div className={`p-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between ${className}`}>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={onToggleSelector}
            leftIcon={isSelectorOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
          >
            {isSelectorOpen ? 'Hide Document List' : 'Select Document'}
          </Button>
          <span className="text-sm text-slate-400">No active document selected for verification</span>
        </div>
        {onNavigateBack && (
          <Button variant="ghost" size="sm" onClick={onNavigateBack} leftIcon={<ArrowLeft className="w-4 h-4" />}>
            Back to Dashboard
          </Button>
        )}
      </div>
    )
  }

  const confidence = formatConfidence(document.extraction?.confidence_score)
  const isProcessing = document.status === 'PROCESSING' || document.status === 'QUEUED'

  const handleConfirmReprocess = async () => {
    setShowConfirmReprocess(false)
    await onReprocess(true)
  }

  const handleSaveClick = () => {
    setShowSavePrompt(true)
  }

  const handleConfirmSave = async () => {
    if (onSaveCorrections) {
      const success = await onSaveCorrections(operatorReason.trim() || undefined)
      if (success) {
        setShowSavePrompt(false)
        setOperatorReason('')
      }
    }
  }

  return (
    <div className={`bg-slate-900 border-b border-slate-800 p-3 sm:p-4 space-y-2 shrink-0 ${className}`}>
      {/* Top Row: Back button, Title, Status Badges, and Action Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Nav actions & Title */}
        <div className="flex items-center gap-2.5 min-w-0">
          {onNavigateBack && (
            <button
              type="button"
              onClick={onNavigateBack}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
              title="Return to Dashboard Overview"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={onToggleSelector}
            className="shrink-0 text-xs px-2.5 py-1"
            title="Toggle Document Selector Panel"
            leftIcon={isSelectorOpen ? <PanelLeftClose className="w-3.5 h-3.5" /> : <PanelLeftOpen className="w-3.5 h-3.5" />}
          >
            <span className="hidden sm:inline">{isSelectorOpen ? 'Close List' : 'Documents'}</span>
          </Button>

          <div className="flex items-center gap-2 truncate">
            <div className="p-1.5 rounded-lg bg-blue-950/60 border border-blue-800/60 text-blue-400 shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div className="truncate">
              <h2 className="text-sm sm:text-base font-semibold text-slate-100 truncate" title={document.filename}>
                {document.filename}
              </h2>
              <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                <span className="uppercase">{document.file_type}</span>
                <span>•</span>
                <span>{formatBytes(document.file_size_bytes)}</span>
                <span>•</span>
                <span>{document.page_count} {document.page_count === 1 ? 'page' : 'pages'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Status Pills, Confidence Gauge, and Operational Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Status Badges */}
          <Badge variant={document.status} size="sm" dot>
            {document.status}
          </Badge>

          <Badge variant={document.validation_status} size="sm">
            {document.validation_status}
          </Badge>

          {/* Confidence Score Pill */}
          {document.extraction?.confidence_score !== null && document.extraction?.confidence_score !== undefined && (
            <div
              className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs font-mono font-medium ${
                confidence.variant === 'success'
                  ? 'bg-emerald-950/70 text-emerald-300 border-emerald-800/80'
                  : confidence.variant === 'warning'
                  ? 'bg-amber-950/70 text-amber-300 border-amber-800/80'
                  : 'bg-rose-950/70 text-rose-300 border-rose-800/80'
              }`}
              title={`LLM Model Extraction Confidence: ${confidence.label}`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Score: {confidence.label}</span>
            </div>
          )}

          {/* Layout Mode Switcher */}
          <div className="hidden md:flex items-center bg-slate-950 rounded-lg p-0.5 border border-slate-800 text-slate-400">
            <button
              type="button"
              onClick={() => onChangeLayoutMode('source-focus')}
              className={`p-1.5 rounded transition-colors ${layoutMode === 'source-focus' ? 'bg-slate-800 text-white' : 'hover:text-slate-200'}`}
              title="Source Focus (65% Source / 35% Structured)"
            >
              <Columns className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onChangeLayoutMode('split')}
              className={`p-1.5 rounded transition-colors ${layoutMode === 'split' ? 'bg-slate-800 text-white' : 'hover:text-slate-200'}`}
              title="Split 50/50 View"
            >
              <Layout className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onChangeLayoutMode('data-focus')}
              className={`p-1.5 rounded transition-colors ${layoutMode === 'data-focus' ? 'bg-slate-800 text-white' : 'hover:text-slate-200'}`}
              title="Data Focus (35% Source / 65% Structured)"
            >
              <Columns className="w-3.5 h-3.5 rotate-180" />
            </button>
          </div>

          {/* Refresh Action */}
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors border border-slate-800"
            title="Refresh document status and extractions"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {/* Reprocess Trigger Button */}
          {!isEditMode && (
            <div className="relative">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowConfirmReprocess((v) => !v)}
                isLoading={isReprocessing}
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                className="text-xs"
              >
                Reprocess
              </Button>

              {/* Reprocess Confirmation Popover */}
              {showConfirmReprocess && (
                <div className="absolute right-0 top-full mt-2 w-72 p-3 bg-slate-950 border border-slate-800 rounded-xl shadow-xl z-50 space-y-2 text-xs">
                  <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                    <RotateCcw className="w-3.5 h-3.5 text-brand-400" />
                    <span>Reprocess this document?</span>
                  </div>
                  <p className="text-slate-400 leading-relaxed text-[11px]">
                    This will re-enqueue async Celery OCR extraction, entity parsing, and arithmetic validation.
                  </p>
                  <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-800">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowConfirmReprocess(false)}
                      className="text-xs px-2 py-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleConfirmReprocess}
                      className="text-xs px-2.5 py-1"
                    >
                      Confirm Reprocess
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TASK-017: Manual Correction Controls */}
          {!isProcessing && (
            <>
              {!isEditMode ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onToggleEditMode}
                  leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                  className="text-xs bg-brand-600 hover:bg-brand-500 text-white"
                  title="Enable manual correction of extracted entities and line items"
                >
                  Edit Corrections
                </Button>
              ) : (
                <div className="flex items-center gap-2">
                  {/* Unsaved changes badge */}
                  <span
                    className={`px-2 py-1 rounded-md text-[11px] font-mono flex items-center gap-1.5 border ${
                      isDirty
                        ? 'bg-amber-950/70 text-amber-300 border-amber-700/80'
                        : 'bg-slate-800/80 text-slate-400 border-slate-700'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${isDirty ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'}`} />
                    <span>{isDirty ? `Unsaved (${dirtyFieldCount})` : 'No changes'}</span>
                  </span>

                  {/* Cancel editing button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onCancelEditing}
                    leftIcon={<Undo2 className="w-3.5 h-3.5" />}
                    className="text-xs text-slate-300 border-slate-700"
                  >
                    Cancel
                  </Button>

                  {/* Save button with Popover */}
                  <div className="relative">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleSaveClick}
                      disabled={!isDirty || isSavingCorrection}
                      isLoading={isSavingCorrection}
                      leftIcon={<Save className="w-3.5 h-3.5" />}
                      className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
                    >
                      Save Corrections
                    </Button>

                    {showSavePrompt && (
                      <div className="absolute right-0 top-full mt-2 w-80 p-3.5 bg-slate-950 border border-slate-800 rounded-xl shadow-2xl z-50 space-y-3 text-xs">
                        <div className="font-semibold text-slate-100 flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <Save className="w-4 h-4 text-emerald-400" />
                            <span>Save Manual Corrections</span>
                          </span>
                          <button
                            type="button"
                            onClick={() => setShowSavePrompt(false)}
                            className="text-slate-400 hover:text-slate-200"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        <p className="text-slate-400 text-[11px] leading-relaxed">
                          Applying these modifications will update the structured extraction, recalculate validation findings, and write an immutable audit log.
                        </p>

                        <div>
                          <label className="text-[10px] text-slate-300 uppercase font-medium block mb-1">
                            Reason for modification (optional)
                          </label>
                          <input
                            type="text"
                            aria-label="Reason for modification"
                            value={operatorReason}
                            onChange={(e) => setOperatorReason(e.target.value)}
                            placeholder="e.g. Corrected subtotal OCR typo"
                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                          />
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-800">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowSavePrompt(false)}
                            className="text-xs px-2.5 py-1 text-slate-400"
                          >
                            Cancel
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={handleConfirmSave}
                            isLoading={isSavingCorrection}
                            className="text-xs px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white"
                          >
                            Confirm & Save
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Notifications row for reprocess status and correction status */}
      {reprocessMessage && (
        <div className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-900/60 px-3 py-1.5 rounded-lg flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          <span>{reprocessMessage}</span>
        </div>
      )}

      {reprocessError && (
        <div className="text-[11px] font-mono text-rose-400 bg-rose-950/40 border border-rose-900/60 px-3 py-1.5 rounded-lg">
          {reprocessError}
        </div>
      )}

      {correctionSuccessMessage && (
        <div className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-900/60 px-3 py-1.5 rounded-lg flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          <span>{correctionSuccessMessage}</span>
        </div>
      )}

      {correctionError && (
        <div className="text-[11px] font-mono text-rose-400 bg-rose-950/40 border border-rose-900/60 px-3 py-1.5 rounded-lg">
          {correctionError}
        </div>
      )}
    </div>
  )
}
