import React from 'react'
import type { PaneLayoutMode } from './ReviewWorkspaceHeader'

export interface DualPaneViewerProps {
  layoutMode: PaneLayoutMode
  leftPane: React.ReactNode
  rightPane: React.ReactNode
  className?: string
}

export const DualPaneViewer: React.FC<DualPaneViewerProps> = ({
  layoutMode,
  leftPane,
  rightPane,
  className = '',
}) => {
  // Grid layout classes based on mode
  const getGridClasses = () => {
    switch (layoutMode) {
      case 'source-focus':
        return 'grid-cols-1 lg:grid-cols-12'
      case 'data-focus':
        return 'grid-cols-1 lg:grid-cols-12'
      case 'split':
      default:
        return 'grid-cols-1 lg:grid-cols-2'
    }
  }

  const getLeftSpan = () => {
    switch (layoutMode) {
      case 'source-focus':
        return 'lg:col-span-7'
      case 'data-focus':
        return 'lg:col-span-4'
      case 'split':
      default:
        return ''
    }
  }

  const getRightSpan = () => {
    switch (layoutMode) {
      case 'source-focus':
        return 'lg:col-span-5'
      case 'data-focus':
        return 'lg:col-span-8'
      case 'split':
      default:
        return ''
    }
  }

  return (
    <div className={`grid gap-4 flex-1 min-h-0 p-3 sm:p-4 overflow-hidden ${getGridClasses()} ${className}`}>
      {/* Left Pane (Source Text & Evidence Grounding) */}
      <div className={`flex flex-col min-h-[380px] lg:min-h-0 h-full overflow-hidden ${getLeftSpan()}`}>
        {leftPane}
      </div>

      {/* Right Pane (Structured Entities, Line Items, Validations, Audit) */}
      <div className={`flex flex-col min-h-[420px] lg:min-h-0 h-full overflow-hidden ${getRightSpan()}`}>
        {rightPane}
      </div>
    </div>
  )
}
