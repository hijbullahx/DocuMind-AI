import React from 'react'
import { FileSpreadsheet, FileText, History, ShieldAlert } from 'lucide-react'
import { HeaderEntitiesCard } from './HeaderEntitiesCard'
import { LineItemsTable } from './LineItemsTable'
import { ValidationFindingsList } from './ValidationFindingsList'
import { AuditHistoryCard } from './AuditHistoryCard'
import type { EditableExtractionDraft, ReviewTab } from '@/hooks/useDocumentReview'
import type { DocumentDetail, LineItemCorrectionPayload } from '@/types/document'

export interface StructuredExtractionPaneProps {
  document: DocumentDetail
  activeTab: ReviewTab
  onTabChange: (tab: ReviewTab) => void
  activeEvidenceKey: string | null
  onHighlightEvidence: (key: string, quote: string | null) => void

  // TASK-017: Edit & Correction Props
  isEditMode?: boolean
  draft?: EditableExtractionDraft
  onUpdateDraftField?: (
    field: keyof Omit<EditableExtractionDraft, 'line_items'>,
    value: string | number | null
  ) => void
  onAutoCalculateTotal?: () => void
  onUpdateDraftLineItem?: (
    index: number,
    updatedItem: Partial<LineItemCorrectionPayload>
  ) => void
  onAddDraftLineItem?: () => void
  onRemoveDraftLineItem?: (index: number) => void
  onApplyCalculatedSubtotal?: () => void

  className?: string
}

export const StructuredExtractionPane: React.FC<StructuredExtractionPaneProps> = ({
  document,
  activeTab,
  onTabChange,
  activeEvidenceKey,
  onHighlightEvidence,
  isEditMode = false,
  draft,
  onUpdateDraftField,
  onAutoCalculateTotal,
  onUpdateDraftLineItem,
  onAddDraftLineItem,
  onRemoveDraftLineItem,
  onApplyCalculatedSubtotal,
  className = '',
}) => {
  const extraction = document.extraction
  const lineItems = isEditMode && draft ? draft.line_items : extraction?.line_items || []
  const validationErrors = document.validation_errors || []
  const auditLogs = document.audit_logs || []

  const errorCount = validationErrors.filter((e) => e.severity === 'ERROR').length
  const warningCount = validationErrors.filter((e) => e.severity === 'WARNING').length

  const tabs: { key: ReviewTab; label: string; icon: React.ReactNode; badge?: React.ReactNode }[] = [
    {
      key: 'fields',
      label: 'Fields',
      icon: <FileText className="w-4 h-4" />,
      badge: isEditMode ? (
        <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 text-[10px] font-mono border border-amber-500/30">
          EDIT
        </span>
      ) : undefined,
    },
    {
      key: 'items',
      label: 'Line Items',
      icon: <FileSpreadsheet className="w-4 h-4" />,
      badge: (
        <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono">
          {lineItems.length}
        </span>
      ),
    },
    {
      key: 'validations',
      label: 'Validations',
      icon: <ShieldAlert className="w-4 h-4" />,
      badge: validationErrors.length > 0 ? (
        <span
          className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold ${
            errorCount > 0
              ? 'bg-rose-950 text-rose-300 border border-rose-800/80'
              : warningCount > 0
              ? 'bg-amber-950 text-amber-300 border border-amber-800/80'
              : 'bg-blue-950 text-blue-300 border border-blue-800/80'
          }`}
        >
          {validationErrors.length}
        </span>
      ) : undefined,
    },
    {
      key: 'audit',
      label: 'Audit & Info',
      icon: <History className="w-4 h-4" />,
      badge: auditLogs.length > 0 ? (
        <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 text-[10px] font-mono">
          {auditLogs.length}
        </span>
      ) : undefined,
    },
  ]

  return (
    <div className={`flex flex-col h-full bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden ${className}`}>
      {/* Tab Navigation Bar */}
      <div className="flex items-center gap-1 p-2 bg-slate-950/80 border-b border-slate-800 overflow-x-auto shrink-0">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onTabChange(tab.key)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all select-none whitespace-nowrap ${
                isActive
                  ? 'bg-brand-600/90 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <span className={isActive ? 'text-white' : 'text-slate-500'}>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.badge}
            </button>
          )
        })}
      </div>

      {/* Tab Content Body with independent scroll */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5">
        {activeTab === 'fields' && (
          <HeaderEntitiesCard
            document={document}
            isEditMode={isEditMode}
            draft={draft}
            onUpdateDraftField={onUpdateDraftField}
            onAutoCalculateTotal={onAutoCalculateTotal}
            activeEvidenceKey={activeEvidenceKey}
            onHighlightEvidence={onHighlightEvidence}
          />
        )}

        {activeTab === 'items' && (
          <LineItemsTable
            items={extraction?.line_items || []}
            currency={isEditMode && draft ? draft.currency : (extraction?.currency || 'USD')}
            statedSubtotal={
              isEditMode && draft
                ? draft.subtotal
                : (extraction?.subtotal !== null && extraction?.subtotal !== undefined
                    ? Number(extraction.subtotal)
                    : null)
            }
            isEditMode={isEditMode}
            draftItems={draft?.line_items}
            onUpdateItem={onUpdateDraftLineItem}
            onAddItem={onAddDraftLineItem}
            onRemoveItem={onRemoveDraftLineItem}
            onApplyCalculatedSubtotal={onApplyCalculatedSubtotal}
          />
        )}

        {activeTab === 'validations' && (
          <ValidationFindingsList findings={validationErrors} />
        )}

        {activeTab === 'audit' && (
          <AuditHistoryCard document={document} />
        )}
      </div>
    </div>
  )
}
