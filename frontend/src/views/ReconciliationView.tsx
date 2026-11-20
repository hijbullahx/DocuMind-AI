import React, { useState } from 'react'
import {
  GitCompare,
  History,
  RotateCcw,
  Sparkles,
  Layers,
  FileSpreadsheet,
  AlertTriangle,
} from 'lucide-react'
import { useReconciliation } from '@/hooks/useReconciliation'
import { DualDocumentSelector } from '@/components/reconciliation/DualDocumentSelector'
import { ReconciliationSummaryBanner } from '@/components/reconciliation/ReconciliationSummaryBanner'
import { FieldComparisonMatrix } from '@/components/reconciliation/FieldComparisonMatrix'
import { LineItemsReconciliationTable } from '@/components/reconciliation/LineItemsReconciliationTable'
import { DiscrepancyFindingsList } from '@/components/reconciliation/DiscrepancyFindingsList'
import { ReconciliationHistoryDrawer } from '@/components/reconciliation/ReconciliationHistoryDrawer'

export interface ReconciliationViewProps {
  className?: string
}

type TabType = 'all' | 'fields' | 'items' | 'discrepancies'

export const ReconciliationView: React.FC<ReconciliationViewProps> = ({ className = '' }) => {
  const {
    selectedDocA,
    selectedDocB,
    tolerance,
    currentResult,
    isReconciling,
    reconciliationError,
    history,
    isLoadingHistory,
    executeReconciliation,
    reReconcileCurrent,
    loadReconciliationById,
    setSelectedDocA,
    setSelectedDocB,
    setTolerance,
    swapDocuments,
    resetSelection,
  } = useReconciliation()

  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>('all')

  const totalDiscrepancies =
    (currentResult?.discrepancies.length || 0) + (currentResult?.warnings.length || 0)

  return (
    <div className={`space-y-6 max-w-7xl mx-auto pb-16 ${className}`}>
      {/* Top Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-2xl shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
            <GitCompare className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                Cross-Document Reconciliation Workbench
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-brand-950/80 text-brand-300 border border-brand-800/50">
                TASK-018
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic multi-document financial matching, line item pairing, and discrepancy detection.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* History Drawer Trigger */}
          <button
            onClick={() => setIsHistoryOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800 text-slate-200 hover:bg-slate-700/80 hover:text-white transition-colors border border-slate-700"
          >
            <History className="w-4 h-4 text-slate-400" />
            <span>Audit History</span>
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-slate-900 text-brand-300 font-mono">
              {history.length}
            </span>
          </button>

          {/* Reset Selection */}
          {(selectedDocA || selectedDocB || currentResult) && (
            <button
              onClick={resetSelection}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors border border-transparent"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Error Alert if any */}
      {reconciliationError && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 flex items-center gap-3 text-rose-300 text-xs">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <div className="flex-1">
            <span className="font-semibold">Reconciliation Error:</span> {reconciliationError}
          </div>
        </div>
      )}

      {/* 1. Document Selection & Options Panel */}
      <DualDocumentSelector
        selectedDocA={selectedDocA}
        selectedDocB={selectedDocB}
        onSelectDocA={setSelectedDocA}
        onSelectDocB={setSelectedDocB}
        onSwapDocuments={swapDocuments}
        onReset={resetSelection}
        tolerance={tolerance}
        onChangeTolerance={setTolerance}
        onRunReconciliation={executeReconciliation}
        isReconciling={isReconciling}
      />

      {/* 2. Reconciliation Results View */}
      {currentResult ? (
        <div className="space-y-6">
          {/* Summary Banner */}
          <ReconciliationSummaryBanner
            record={currentResult}
            onReReconcile={reReconcileCurrent}
            isReReconciling={isReconciling}
          />

          {/* View Mode Tabs */}
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === 'all'
                  ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Complete Overview
            </button>
            <button
              onClick={() => setActiveTab('fields')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
                activeTab === 'fields'
                  ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Financial Fields</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">
                {currentResult.comparison_matrix?.length || 0}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('items')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
                activeTab === 'items'
                  ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>Line Items</span>
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">
                {currentResult.matched_items_count + currentResult.unmatched_items_count}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('discrepancies')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
                activeTab === 'discrepancies'
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Discrepancies</span>
              {totalDiscrepancies > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-rose-950 text-rose-300 border border-rose-800/40 font-mono">
                  {totalDiscrepancies}
                </span>
              )}
            </button>
          </div>

          {/* Section 1: Financial and Entity Field Comparison Matrix */}
          {(activeTab === 'all' || activeTab === 'fields') && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-4 h-4 text-brand-400" />
                <h3 className="text-sm font-bold text-slate-200">
                  Financial & Entity Field Matrix
                </h3>
              </div>
              <FieldComparisonMatrix record={currentResult} />
            </div>
          )}

          {/* Section 2: Tabular Line Items Reconciliation */}
          {(activeTab === 'all' || activeTab === 'items') && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <FileSpreadsheet className="w-4 h-4 text-brand-400" />
                <h3 className="text-sm font-bold text-slate-200">
                  Line Items Cross-Reconciliation
                </h3>
              </div>
              <LineItemsReconciliationTable record={currentResult} />
            </div>
          )}

          {/* Section 3: Discrepancy Findings & Action Items */}
          {(activeTab === 'all' || activeTab === 'discrepancies') && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-slate-200">
                  Audit Findings & Discrepancies
                </h3>
              </div>
              <DiscrepancyFindingsList
                discrepancies={currentResult.discrepancies}
                warnings={currentResult.warnings}
              />
            </div>
          )}
        </div>
      ) : (
        /* Empty State before running reconciliation */
        <div className="bg-slate-900 border border-dashed border-slate-800 rounded-2xl p-12 text-center max-w-2xl mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mx-auto mb-4 text-brand-400">
            <GitCompare className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-white mb-2">
            Multi-Document Reconciliation Ready
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed max-w-md mx-auto mb-6">
            Select two processed documents above (e.g. an Invoice and its Purchase Order, or two recurring billing invoices) to compare financial totals, dates, suppliers, and line items with tolerance checking.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-left">
            <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <div className="text-xs font-semibold text-brand-300 mb-1 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-brand-400" /> 1. Human Corrections
              </div>
              <p className="text-[11px] text-slate-500">
                Transparently reflects human-edited values from TASK-017 alongside AI raw values.
              </p>
            </div>
            <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <div className="text-xs font-semibold text-brand-300 mb-1 flex items-center gap-1.5">
                <FileSpreadsheet className="w-3.5 h-3.5 text-brand-400" /> 2. Line Items
              </div>
              <p className="text-[11px] text-slate-500">
                Matches line items via Jaccard token overlap and flags quantities & rates.
              </p>
            </div>
            <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <div className="text-xs font-semibold text-brand-300 mb-1 flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-brand-400" /> 3. Persistent History
              </div>
              <p className="text-[11px] text-slate-500">
                Stores reconciliation records in the database with 1-click reload and re-verification.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* History Slide-Over Drawer */}
      <ReconciliationHistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        history={history}
        onSelectRecord={loadReconciliationById}
        currentRecordId={currentResult?.id}
        isLoading={isLoadingHistory}
      />
    </div>
  )
}
