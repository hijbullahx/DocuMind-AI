import React, { useEffect, useState } from 'react'
import { DocumentReviewSelector } from '@/components/review/DocumentReviewSelector'
import { DualPaneViewer } from '@/components/review/DualPaneViewer'
import { EmptyOrProcessingState } from '@/components/review/EmptyOrProcessingState'
import {
  type PaneLayoutMode,
  ReviewWorkspaceHeader,
} from '@/components/review/ReviewWorkspaceHeader'
import { SourceDocumentPane } from '@/components/review/SourceDocumentPane'
import { StructuredExtractionPane } from '@/components/review/StructuredExtractionPane'
import { useDocumentReview } from '@/hooks/useDocumentReview'
import { useDocumentSelector } from '@/hooks/useDocumentSelector'

export interface ReviewWorkbenchViewProps {
  initialDocumentId?: string | null
  onNavigateBack?: () => void
  className?: string
}

export const ReviewWorkbenchView: React.FC<ReviewWorkbenchViewProps> = ({
  initialDocumentId = null,
  onNavigateBack,
  className = '',
}) => {
  const [selectedId, setSelectedId] = useState<string | null>(initialDocumentId)
  const [isSelectorOpen, setIsSelectorOpen] = useState<boolean>(!initialDocumentId)
  const [layoutMode, setLayoutMode] = useState<PaneLayoutMode>('split')

  // Document Selector hook
  const {
    documents,
    totalCount,
    isLoading: isSelectorLoading,
    error: selectorError,
    search: selectorSearch,
    setSearch: setSelectorSearch,
    validationStatus,
    setValidationStatus,
    page,
    setPage,
    totalPages,
    refresh: refreshSelector,
  } = useDocumentSelector()

  // Update selectedId if initialDocumentId changes from parent
  useEffect(() => {
    if (initialDocumentId) {
      setSelectedId(initialDocumentId)
      setIsSelectorOpen(false)
    }
  }, [initialDocumentId])

  // If no document selected yet, pick the first document from list once loaded
  useEffect(() => {
    if (!selectedId && documents.length > 0) {
      setSelectedId(documents[0].id)
    }
  }, [selectedId, documents])

  // Active Document Review hook
  const {
    document,
    isLoading: isReviewLoading,
    error: reviewError,
    isReprocessing,
    reprocessMessage,
    reprocessError,
    activeEvidenceKey,
    activeEvidenceQuote,
    setEvidenceHighlight,
    clearEvidenceHighlight,
    searchQuery,
    setSearchQuery,
    activeTab,
    setActiveTab,
    refresh: refreshDocument,
    reprocess,
  } = useDocumentReview(selectedId)

  const handleSelectDocument = (id: string) => {
    setSelectedId(id)
    // On small screens, close the drawer after selection
    if (window.innerWidth < 768) {
      setIsSelectorOpen(false)
    }
  }

  const handleRefreshAll = async () => {
    await Promise.all([refreshDocument(), refreshSelector()])
  }

  return (
    <div className={`flex h-[calc(100vh-4rem)] overflow-hidden bg-slate-950 ${className}`}>
      {/* Collapsible Document Selector Panel */}
      {isSelectorOpen && (
        <DocumentReviewSelector
          documents={documents}
          totalCount={totalCount}
          selectedId={selectedId}
          onSelectDocument={handleSelectDocument}
          isLoading={isSelectorLoading}
          error={selectorError}
          search={selectorSearch}
          onSearchChange={setSelectorSearch}
          validationStatus={validationStatus}
          onValidationStatusChange={setValidationStatus}
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
          onRefresh={refreshSelector}
          onClose={() => setIsSelectorOpen(false)}
        />
      )}

      {/* Main Review Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Workbench Header */}
        <ReviewWorkspaceHeader
          document={document}
          isSelectorOpen={isSelectorOpen}
          onToggleSelector={() => setIsSelectorOpen((v) => !v)}
          layoutMode={layoutMode}
          onChangeLayoutMode={setLayoutMode}
          onRefresh={handleRefreshAll}
          onReprocess={reprocess}
          isReprocessing={isReprocessing}
          reprocessMessage={reprocessMessage}
          reprocessError={reprocessError}
          onNavigateBack={onNavigateBack}
        />

        {/* Content Body */}
        {isReviewLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyOrProcessingState
              type="processing"
              title="Loading Document Review..."
              description="Retrieving source text, structured extraction fields, and mathematical validation findings."
            />
          </div>
        ) : reviewError ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <EmptyOrProcessingState
              type="failed"
              title="Unable to Load Document"
              errorMessage={reviewError}
              onRefresh={refreshDocument}
            />
          </div>
        ) : !document ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <EmptyOrProcessingState
              type="no-selection"
              title="No Document Selected"
              description="Open the document selector on the left to select an ingested invoice for inspection."
            />
          </div>
        ) : document.status === 'QUEUED' || document.status === 'PROCESSING' ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <EmptyOrProcessingState
              type={document.status === 'QUEUED' ? 'queued' : 'processing'}
              onRefresh={refreshDocument}
            />
          </div>
        ) : (
          <DualPaneViewer
            layoutMode={layoutMode}
            leftPane={
              <SourceDocumentPane
                rawText={document.raw_text}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                activeEvidenceKey={activeEvidenceKey}
                activeEvidenceQuote={activeEvidenceQuote}
                onClearEvidence={clearEvidenceHighlight}
              />
            }
            rightPane={
              <StructuredExtractionPane
                document={document}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                activeEvidenceKey={activeEvidenceKey}
                onHighlightEvidence={setEvidenceHighlight}
              />
            }
          />
        )}
      </div>
    </div>
  )
}
