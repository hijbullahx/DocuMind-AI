<<<<<<< HEAD
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
=======
import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <section id="center">
        <div className="hero">
          <img src={heroImg} className="base" width="170" height="179" alt="" />
          <img src={reactLogo} className="framework" alt="React logo" />
          <img src={viteLogo} className="vite" alt="Vite logo" />
        </div>
        <div>
          <h1>Get started</h1>
          <p>
            Edit <code>src/App.tsx</code> and save to test <code>HMR</code>
          </p>
        </div>
        <button
          type="button"
          className="counter"
          onClick={() => setCount((count) => count + 1)}
        >
          Count is {count}
        </button>
      </section>

      <div className="ticks"></div>

      <section id="next-steps">
        <div id="docs">
          <svg className="icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#documentation-icon"></use>
          </svg>
          <h2>Documentation</h2>
          <p>Your questions, answered</p>
          <ul>
            <li>
              <a href="https://vite.dev/" target="_blank">
                <img className="logo" src={viteLogo} alt="" />
                Explore Vite
              </a>
            </li>
            <li>
              <a href="https://react.dev/" target="_blank">
                <img className="button-icon" src={reactLogo} alt="" />
                Learn more
              </a>
            </li>
          </ul>
        </div>
        <div id="social">
          <svg className="icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#social-icon"></use>
          </svg>
          <h2>Connect with us</h2>
          <p>Join the Vite community</p>
          <ul>
            <li>
              <a href="https://github.com/vitejs/vite" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#github-icon"></use>
                </svg>
                GitHub
              </a>
            </li>
            <li>
              <a href="https://chat.vite.dev/" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#discord-icon"></use>
                </svg>
                Discord
              </a>
            </li>
            <li>
              <a href="https://x.com/vite_js" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#x-icon"></use>
                </svg>
                X.com
              </a>
            </li>
            <li>
              <a href="https://bsky.app/profile/vite.dev" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#bluesky-icon"></use>
                </svg>
                Bluesky
              </a>
            </li>
          </ul>
        </div>
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
    </>
>>>>>>> 59d0226b1fea53a8251c95a40f763b863dbbf693
  )
}

export default App
