import React from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Files,
  Upload,
  XCircle,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import type { QueueSummary } from '@/types/upload'

export interface QueueSummaryCardsProps {
  summary: QueueSummary
}

export const QueueSummaryCards: React.FC<QueueSummaryCardsProps> = ({ summary }) => {
  const cards = [
    {
      label: 'Total Queued',
      value: summary.total,
      icon: <Files className="w-4 h-4 text-slate-300" />,
      border: 'border-slate-800 bg-slate-900/60',
      valueColor: 'text-white',
    },
    {
      label: 'Uploading',
      value: summary.uploading,
      icon: <Upload className="w-4 h-4 text-brand-400 animate-bounce" />,
      border: 'border-brand-500/30 bg-brand-950/20',
      valueColor: 'text-brand-300',
    },
    {
      label: 'Celery Processing',
      value: summary.processing,
      icon: <Clock className="w-4 h-4 text-blue-400 animate-spin" />,
      border: 'border-blue-500/30 bg-blue-950/20',
      valueColor: 'text-blue-300',
    },
    {
      label: 'Verified Clean',
      value: summary.verified,
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
      border: 'border-emerald-500/30 bg-emerald-950/20',
      valueColor: 'text-emerald-300',
    },
    {
      label: 'Needs Review',
      value: summary.needsReview,
      icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
      border: 'border-amber-500/30 bg-amber-950/20',
      valueColor: 'text-amber-300',
    },
    {
      label: 'Failed / Rejected',
      value: summary.failed,
      icon: <XCircle className="w-4 h-4 text-rose-400" />,
      border: 'border-rose-500/30 bg-rose-950/20',
      valueColor: 'text-rose-300',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c, idx) => (
        <Card key={idx} className={`border ${c.border} shadow-sm`}>
          <CardContent className="p-3.5 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span className="truncate">{c.label}</span>
              {c.icon}
            </div>
            <div className={`text-xl font-bold tracking-tight ${c.valueColor}`}>
              {c.value}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
