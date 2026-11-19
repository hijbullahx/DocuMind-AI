import React, { useState } from 'react'
import { Navbar } from './Navbar'
import { Sidebar, type NavItemKey } from './Sidebar'

export interface AppLayoutProps {
  currentView: NavItemKey
  onSelectView: (view: NavItemKey) => void
  backendConnected: boolean
  isCheckingBackend: boolean
  onRefreshMetrics: () => void
  children: React.ReactNode
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentView,
  onSelectView,
  backendConnected,
  isCheckingBackend,
  onRefreshMetrics,
  children,
}) => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Navbar */}
      <Navbar
        backendConnected={backendConnected}
        isCheckingBackend={isCheckingBackend}
        onRefreshMetrics={onRefreshMetrics}
        onToggleSidebar={() => setIsSidebarCollapsed((prev) => !prev)}
      />

      {/* Main Shell (Sidebar + Content Viewport) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <Sidebar
          currentView={currentView}
          onSelectView={onSelectView}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        />

        {/* Content Viewport */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  )
}
