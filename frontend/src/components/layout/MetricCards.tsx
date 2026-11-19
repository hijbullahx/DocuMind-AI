import React from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  XCircle,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import type { DashboardMetrics } from '@/types/document'

export interface MetricCardsProps {
  metrics: DashboardMetrics
  isLoading: boolean
}

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics, isLoading }) => {
  const cards = [
    {
      title: 'Total Ingested',
      value: metrics.total,
      description: 'Documents in system catalog',
      icon: <FileSpreadsheet className="w-5 h-5 text-brand-400" />,
      accent: 'border-brand-500/30 bg-brand-950/20',
      badge: 'All Formats',
    },
    {
      title: 'Processing',
      value: metrics.processing,
      description: 'Ingestion & OCR queue',
      icon: <Clock className="w-5 h-5 text-blue-400 animate-spin" />,
      accent: 'border-blue-500/30 bg-blue-950/20',
      badge: 'Active Celery',
    },
    {
      title: 'Verified Clean',
      value: metrics.verified,
      description: 'Zero math or rule anomalies',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
      accent: 'border-emerald-500/30 bg-emerald-950/20',
      badge: 'Validated',
    },
    {
      title: 'Needs Review',
      value: metrics.needsReview,
      description: 'Math anomalies or warnings',
      icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
      accent: 'border-amber-500/30 bg-amber-950/20',
      badge: 'Operator Attention',
    },
    {
      title: 'Failed / Rejected',
      value: metrics.failed,
      description: 'Processing or validation errors',
      icon: <XCircle className="w-5 h-5 text-rose-400" />,
      accent: 'border-rose-500/30 bg-rose-950/20',
      badge: 'Action Required',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map((card, idx) => (
        <Card
          key={idx}
          className={`border transition-all hover:border-slate-700/80 hover:shadow-lg ${card.accent}`}
        >
          <CardContent className="p-4 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-xs font-medium text-slate-400">{card.title}</span>
              <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
                {card.icon}
              </div>
            </div>

            <div className="my-1">
              {isLoading ? (
                <div className="h-8 w-16 bg-slate-800 animate-pulse rounded my-1" />
              ) : (
                <div className="text-2xl font-bold tracking-tight text-white">
                  {card.value.toLocaleString()}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60">
              <span className="truncate">{card.description}</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
