import React from 'react'
import {
  ChevronLeft,
  ChevronRight,
  FileCheck2,
  GitCompare,
  LayoutDashboard,
  Search,
  UploadCloud,
} from 'lucide-react'

export type NavItemKey = 'dashboard' | 'upload' | 'review' | 'reconcile' | 'search'

export interface SidebarProps {
  currentView: NavItemKey
  onSelectView: (view: NavItemKey) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
}

interface NavItemConfig {
  key: NavItemKey
  label: string
  icon: React.ReactNode
  tag?: string
  isPlanned?: boolean
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  isCollapsed,
  onToggleCollapse,
}) => {
  const navItems: NavItemConfig[] = [
    {
      key: 'dashboard',
      label: 'Dashboard Overview',
      icon: <LayoutDashboard className="w-5 h-5" />,
    },
    {
      key: 'upload',
      label: 'Batch Upload & Queue',
      icon: <UploadCloud className="w-5 h-5" />,
      tag: 'TASK-015',
      isPlanned: true,
    },
    {
      key: 'review',
      label: 'Review Workbench',
      icon: <FileCheck2 className="w-5 h-5" />,
      tag: 'TASK-016',
      isPlanned: true,
    },
    {
      key: 'reconcile',
      label: 'Cross-Reconciliation',
      icon: <GitCompare className="w-5 h-5" />,
      tag: 'TASK-018',
      isPlanned: true,
    },
    {
      key: 'search',
      label: 'Full-Text Search',
      icon: <Search className="w-5 h-5" />,
      tag: 'TASK-018',
      isPlanned: true,
    },
  ]

  return (
    <aside
      className={`bg-slate-900/90 border-r border-slate-800 flex flex-col transition-all duration-300 relative shrink-0 ${
        isCollapsed ? 'w-18' : 'w-64'
      }`}
    >
      {/* Navigation Section */}
      <div className="p-3 flex-1 space-y-1.5">
        <div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          {!isCollapsed && 'Operator Console'}
        </div>

        {navItems.map((item) => {
          const isActive = currentView === item.key

          return (
            <button
              key={item.key}
              onClick={() => onSelectView(item.key)}
              title={isCollapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-medium text-xs transition-all group relative ${
                isActive
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/40 shadow-sm shadow-brand-500/10'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60 border border-transparent'
              }`}
            >
              <span
                className={`shrink-0 transition-colors ${
                  isActive ? 'text-brand-400' : 'text-slate-400 group-hover:text-slate-200'
                }`}
              >
                {item.icon}
              </span>

              {!isCollapsed && (
                <div className="flex-1 flex items-center justify-between text-left truncate">
                  <span className="truncate">{item.label}</span>
                  {item.isPlanned && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700">
                      {item.tag}
                    </span>
                  )}
                </div>
              )}

              {/* Active Indicator Bar */}
              {isActive && (
                <span className="absolute left-0 top-2 bottom-2 w-1 bg-brand-500 rounded-r" />
              )}
            </button>
          )
        })}
      </div>

      {/* Footer / Collapse Toggle */}
      <div className="p-3 border-t border-slate-800/80">
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center gap-2 p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 text-xs font-medium transition-colors"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse Menu</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
