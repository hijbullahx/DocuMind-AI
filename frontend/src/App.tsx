import { useCallback, useEffect, useState } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import type { NavItemKey } from '@/components/layout/Sidebar'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/services/api'
import type { DashboardMetrics, DocumentListItem } from '@/types/document'
import { BatchUploadView } from '@/views/BatchUploadView'
import { DashboardOverview } from '@/views/DashboardOverview'
import { LoginView } from '@/views/LoginView'
import { ModulePlaceholderView } from '@/views/ModulePlaceholderView'
import { ReconciliationView } from '@/views/ReconciliationView'
import { ReviewWorkbenchView } from '@/views/ReviewWorkbenchView'
import { SearchView } from '@/views/SearchView'
import { FileText, Loader2 } from 'lucide-react'

export function App() {
  const {
    user,
    isAuthenticated,
    isLoading: isAuthLoading,
    error: authError,
    login,
    logout,
    clearError,
  } = useAuth()

  const [currentView, setCurrentView] = useState<NavItemKey>('dashboard')
  const [selectedDocumentIdForReview, setSelectedDocumentIdForReview] = useState<string | null>(null)
  const [backendConnected, setBackendConnected] = useState<boolean>(false)
  const [isCheckingBackend, setIsCheckingBackend] = useState<boolean>(true)
  const [isLoadingMetrics, setIsLoadingMetrics] = useState<boolean>(true)
  const [isLoadingRecent, setIsLoadingRecent] = useState<boolean>(true)

  const [metrics, setMetrics] = useState<DashboardMetrics>({
    total: 0,
    processing: 0,
    verified: 0,
    needsReview: 0,
    failed: 0,
  })

  const [recentDocuments, setRecentDocuments] = useState<DocumentListItem[]>([])

  const loadDashboardData = useCallback(async () => {
    setIsCheckingBackend(true)
    setIsLoadingMetrics(true)
    setIsLoadingRecent(true)

    try {
      // 1. Probe backend connectivity (public /health/ endpoint)
      const health = await api.checkBackendHealth()
      setBackendConnected(health.isConnected)

      // 2. Fetch live metrics from real DRF count queries (requires JWT auth)
      const fetchedMetrics = await api.getDashboardMetrics()
      setMetrics(fetchedMetrics)

      // 3. Fetch recent documents
      const docs = await api.getRecentDocuments(5)
      setRecentDocuments(docs)
    } catch {
      setBackendConnected(false)
    } finally {
      setIsCheckingBackend(false)
      setIsLoadingMetrics(false)
      setIsLoadingRecent(false)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      loadDashboardData()
    }
  }, [isAuthenticated, loadDashboardData])

  // 1. Loading splash screen during session validation
  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-brand-500/20 mb-4 animate-pulse">
          <FileText className="w-6 h-6 text-white" />
        </div>
        <div className="flex items-center gap-2 text-slate-300 text-xs font-medium">
          <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
          <span>Verifying secure auditor session...</span>
        </div>
      </div>
    )
  }

  // 2. Authentication Gate: If unauthenticated, render LoginView
  if (!isAuthenticated) {
    return (
      <LoginView
        onLogin={login}
        isLoading={isAuthLoading}
        error={authError}
        onClearError={clearError}
      />
    )
  }

  // 3. Authenticated Application Shell
  return (
    <AppLayout
      currentView={currentView}
      onSelectView={setCurrentView}
      backendConnected={backendConnected}
      isCheckingBackend={isCheckingBackend}
      onRefreshMetrics={loadDashboardData}
      user={user}
      onLogout={logout}
    >
      {currentView === 'dashboard' ? (
        <DashboardOverview
          metrics={metrics}
          recentDocuments={recentDocuments}
          isLoadingMetrics={isLoadingMetrics}
          isLoadingRecent={isLoadingRecent}
          backendConnected={backendConnected}
          onReviewDocument={(id) => {
            setSelectedDocumentIdForReview(id)
            setCurrentView('review')
          }}
        />
      ) : currentView === 'upload' ? (
        <BatchUploadView onRefreshMetrics={loadDashboardData} />
      ) : currentView === 'review' ? (
        <ReviewWorkbenchView
          initialDocumentId={selectedDocumentIdForReview}
          onNavigateBack={() => setCurrentView('dashboard')}
        />
      ) : currentView === 'reconcile' ? (
        <ReconciliationView />
      ) : currentView === 'search' ? (
        <SearchView
          onNavigateToReview={(id) => {
            setSelectedDocumentIdForReview(id)
            setCurrentView('review')
          }}
        />
      ) : (
        <ModulePlaceholderView moduleKey={currentView} />
      )}
    </AppLayout>
  )
}

export default App
