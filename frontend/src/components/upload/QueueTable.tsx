import React from 'react'
import { FileText, Inbox } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { QueueItemRow } from './QueueItemRow'
import { QueueToolbar } from './QueueToolbar'
import type { QueueItem, QueueSummary } from '@/types/upload'

export interface QueueTableProps {
  queue: QueueItem[]
  summary: QueueSummary
  onRemoveItem: (id: string) => void
  onRetryItem: (id: string) => void
  onClearCompleted: () => void
  onRetryFailed: () => void
  onClearQueue: () => void
}

export const QueueTable: React.FC<QueueTableProps> = ({
  queue,
  summary,
  onRemoveItem,
  onRetryItem,
  onClearCompleted,
  onRetryFailed,
  onClearQueue,
}) => {
  return (
    <Card className="border-slate-800 bg-slate-900/60 shadow-md">
      <CardHeader className="py-4 px-6 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-400" />
              <span>Batch Ingestion Queue</span>
            </CardTitle>
            <p className="text-xs text-slate-400 mt-0.5">
              Live status monitoring across client transfer and Celery worker stages
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="px-6 py-2">
          <QueueToolbar
            summary={summary}
            onClearCompleted={onClearCompleted}
            onRetryFailed={onRetryFailed}
            onClearQueue={onClearQueue}
          />
        </div>

        {queue.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider font-semibold text-[10px] border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Document & Format</th>
                  <th className="py-3 px-3">Upload Transfer</th>
                  <th className="py-3 px-3">Ingestion Status</th>
                  <th className="py-3 px-3">Validation Status</th>
                  <th className="py-3 px-3">Diagnostics / Notes</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {queue.map((item) => (
                  <QueueItemRow
                    key={item.id}
                    item={item}
                    onRemove={onRemoveItem}
                    onRetry={onRetryItem}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-14 px-6 text-center space-y-2.5">
            <div className="w-12 h-12 rounded-2xl bg-slate-800/60 border border-slate-700/80 flex items-center justify-center mx-auto text-slate-400">
              <Inbox className="w-6 h-6" />
            </div>
            <div className="text-sm font-medium text-slate-300">
              No documents in the upload queue
            </div>
            <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
              Drag and drop invoices, receipts, or spreadsheets above to begin batch ingestion.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
