import React from 'react'
import { CheckCheck, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { QueueSummary } from '@/types/upload'

export interface QueueToolbarProps {
  summary: QueueSummary
  onClearCompleted: () => void
  onRetryFailed: () => void
  onClearQueue: () => void
}

export const QueueToolbar: React.FC<QueueToolbarProps> = ({
  summary,
  onClearCompleted,
  onRetryFailed,
  onClearQueue,
}) => {
  const completedCount = summary.verified + summary.needsReview

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-2 border-b border-slate-800/80">
      <div className="flex items-center gap-2 text-xs text-slate-300 font-medium">
        <span>Batch Ingestion Queue</span>
        <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono text-[11px] border border-slate-700">
          {summary.total} {summary.total === 1 ? 'file' : 'files'}
        </span>
      </div>

      <div className="flex items-center gap-2">
        {summary.failed > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetryFailed}
            leftIcon={<RefreshCw className="w-3.5 h-3.5 text-amber-400" />}
            title="Retry all failed files in this queue"
          >
            Retry Failed ({summary.failed})
          </Button>
        )}

        {completedCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearCompleted}
            leftIcon={<CheckCheck className="w-3.5 h-3.5 text-emerald-400" />}
            title="Remove completed documents from list"
          >
            Clear Completed ({completedCount})
          </Button>
        )}

        {summary.total > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearQueue}
            leftIcon={<Trash2 className="w-3.5 h-3.5 text-slate-400" />}
            title="Clear entire queue view (does not abort active server tasks)"
            className="text-slate-400 hover:text-rose-300"
          >
            Clear All
          </Button>
        )}
      </div>
    </div>
  )
}
