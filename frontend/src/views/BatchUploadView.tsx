import React from 'react'
import { Sparkles, UploadCloud } from 'lucide-react'
import { Dropzone } from '@/components/upload/Dropzone'
import { QueueSummaryCards } from '@/components/upload/QueueSummaryCards'
import { QueueTable } from '@/components/upload/QueueTable'
import { Toast } from '@/components/ui/Toast'
import { useUploadQueue } from '@/hooks/useUploadQueue'

export interface BatchUploadViewProps {
  onRefreshMetrics?: () => void
}

export const BatchUploadView: React.FC<BatchUploadViewProps> = ({ onRefreshMetrics }) => {
  const {
    queue,
    summary,
    notifications,
    addFiles,
    removeQueuedItem,
    retryItem,
    retryAllFailed,
    clearCompleted,
    clearQueue,
    dismissNotification,
  } = useUploadQueue(onRefreshMetrics)

  return (
    <div className="space-y-6">
      {/* Toast Alert Feed */}
      {notifications.length > 0 && (
        <div className="space-y-2">
          {notifications.map((n) => (
            <Toast
              key={n.id}
              message={n.message}
              type={n.type}
              onClose={() => dismissNotification(n.id)}
            />
          ))}
        </div>
      )}

      {/* Page Title & Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <span>Batch Document Ingestion</span>
            <span className="p-1 rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20">
              <Sparkles className="w-4 h-4" />
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            High-throughput multi-format upload zone with client-side validation, Celery queue status polling, and real-time processing metrics.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
          <UploadCloud className="w-4 h-4 text-brand-400" />
          <span className="text-slate-400 font-medium">Batch Concurrency:</span>
          <span className="text-brand-300 font-semibold font-mono">2 Parallel Slots</span>
        </div>
      </div>

      {/* Queue Metrics Summary */}
      <QueueSummaryCards summary={summary} />

      {/* Upload Dropzone */}
      <Dropzone onFilesSelected={addFiles} />

      {/* Queue Table */}
      <QueueTable
        queue={queue}
        summary={summary}
        onRemoveItem={removeQueuedItem}
        onRetryItem={retryItem}
        onClearCompleted={clearCompleted}
        onRetryFailed={retryAllFailed}
        onClearQueue={clearQueue}
      />
    </div>
  )
}
