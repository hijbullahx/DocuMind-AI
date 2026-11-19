import { useCallback, useEffect, useState } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import type { NavItemKey } from '@/components/layout/Sidebar'
import { api } from '@/services/api'
import type { DashboardMetrics, DocumentListItem } from '@/types/document'
import { DashboardOverview } from '@/views/DashboardOverview'
import { ModulePlaceholderView } from '@/views/ModulePlaceholderView'

export function App() {
  const [currentView, setCurrentView] = useState<NavItemKey>('dashboard')
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
      // 1. Probe backend connectivity
      const health = await api.checkBackendHealth()
      setBackendConnected(health.isConnected)

      // 2. Fetch live metrics from real DRF count queries
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
    loadDashboardData()
  }, [loadDashboardData])

  return (
    <AppLayout
      currentView={currentView}
      onSelectView={setCurrentView}
      backendConnected={backendConnected}
      isCheckingBackend={isCheckingBackend}
      onRefreshMetrics={loadDashboardData}
    >
      {currentView === 'dashboard' ? (
        <DashboardOverview
          metrics={metrics}
          recentDocuments={recentDocuments}
          isLoadingMetrics={isLoadingMetrics}
          isLoadingRecent={isLoadingRecent}
          backendConnected={backendConnected}
        />
      ) : (
        <ModulePlaceholderView moduleKey={currentView} />
      )}
    </AppLayout>
  )
}

export default App
