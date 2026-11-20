import React from 'react'
import {
  Activity,
  Cpu,
  Database,
  FileText,
  Layers,
  Sparkles,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { MetricCards } from '@/components/layout/MetricCards'
import type { DashboardMetrics, DocumentListItem } from '@/types/document'

export interface DashboardOverviewProps {
  metrics: DashboardMetrics
  recentDocuments: DocumentListItem[]
  isLoadingMetrics: boolean
  isLoadingRecent: boolean
  backendConnected: boolean
  onReviewDocument?: (id: string) => void
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  metrics,
  recentDocuments,
  isLoadingMetrics,
  isLoadingRecent,
  backendConnected,
  onReviewDocument,
}) => {
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  const formatDateTime = (isoString: string) => {
    try {
      const d = new Date(isoString)
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Title & Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <span>Operational Document Intelligence</span>
            <span className="p-1 rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20">
              <Sparkles className="w-4 h-4" />
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Real-time ingestion monitoring, deterministic arithmetic validation, and reconciliation queue.
          </p>
        </div>

        {/* Global Pipeline Health Pill */}
        <div className="flex items-center gap-2 self-start sm:self-auto px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
          <Activity className="w-4 h-4 text-brand-400" />
          <span className="text-slate-400 font-medium">Pipeline Status:</span>
          <span className="text-slate-200 font-semibold">
            {backendConnected ? 'Active / Ingestion Ready' : 'Backend Standby'}
          </span>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <MetricCards metrics={metrics} isLoading={isLoadingMetrics} />

      {/* Main Grid: Pipeline Architecture Services & Recent Documents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Recent Ingested Documents (2/3 width on desktop) */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <FileText className="w-4 h-4 text-brand-400" />
                  <span>Recent Ingested Documents</span>
                </CardTitle>
                <p className="text-xs text-slate-400 mt-0.5">
                  Latest files ingested and processed across the pipeline
                </p>
              </div>
              <Badge variant="neutral" size="sm">
                Live DRF API
              </Badge>
            </CardHeader>

            <CardContent className="p-0">
              {isLoadingRecent ? (
                <div className="p-6 space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-12 bg-slate-800/60 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : recentDocuments.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800/80 font-medium uppercase tracking-wider text-[10px]">
                      <tr>
                        <th className="py-3 px-4">Filename</th>
                        <th className="py-3 px-3">Type</th>
                        <th className="py-3 px-3">Size</th>
                        <th className="py-3 px-3">Ingestion Status</th>
                        <th className="py-3 px-3">Validation Status</th>
                        <th className="py-3 px-4 text-right">Timestamp</th>
                        <th className="py-3 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-slate-300">
                      {recentDocuments.map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4 font-medium text-slate-100 flex items-center gap-2 truncate max-w-[220px]">
                            <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span className="truncate" title={doc.filename}>
                              {doc.filename}
                            </span>
                          </td>
                          <td className="py-3 px-3 uppercase font-mono text-[11px] text-slate-400">
                            {doc.file_type}
                          </td>
                          <td className="py-3 px-3 text-slate-400">
                            {formatBytes(doc.file_size_bytes)}
                          </td>
                          <td className="py-3 px-3">
                            <Badge variant={doc.status} size="sm" dot>
                              {doc.status}
                            </Badge>
                          </td>
                          <td className="py-3 px-3">
                            <Badge variant={doc.validation_status} size="sm">
                              {doc.validation_status}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 text-right text-slate-400 text-[11px] whitespace-nowrap">
                            {formatDateTime(doc.created_at)}
                          </td>
                          <td className="py-3 px-3 text-right whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => onReviewDocument?.(doc.id)}
                              className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-brand-600 text-slate-300 hover:text-white transition-colors text-xs font-medium"
                              title={`Review ${doc.filename} in Side-by-Side Workbench`}
                            >
                              Review
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-12 px-6 text-center space-y-2">
                  <FileText className="w-10 h-10 text-slate-600 mx-auto" />
                  <p className="text-sm font-medium text-slate-300">
                    No documents ingested yet
                  </p>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    {backendConnected
                      ? 'The database is currently empty. Upload documents in TASK-015 to start processing.'
                      : 'Connecting to backend... Ensure the Django server is running at localhost:8000.'}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Engine Stack & Architecture Diagnostics (1/3 width) */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Cpu className="w-4 h-4 text-brand-400" />
                <span>Engine Services</span>
              </CardTitle>
              <p className="text-xs text-slate-400 mt-0.5">
                Active processing pipeline modules
              </p>
            </CardHeader>

            <CardContent className="p-4 space-y-3 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="flex items-center gap-2.5">
                  <Layers className="w-4 h-4 text-indigo-400 shrink-0" />
                  <div>
                    <div className="font-semibold text-slate-200">Multi-Format Ingestion</div>
                    <div className="text-[11px] text-slate-400">PDF, OCR, OpenPyXL, CSV</div>
                  </div>
                </div>
                <Badge variant="success" size="sm">Active</Badge>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="flex items-center gap-2.5">
                  <Sparkles className="w-4 h-4 text-brand-400 shrink-0" />
                  <div>
                    <div className="font-semibold text-slate-200">Zero-Hallucination LLM</div>
                    <div className="text-[11px] text-slate-400">Structured Pydantic Output</div>
                  </div>
                </div>
                <Badge variant="success" size="sm">Active</Badge>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="flex items-center gap-2.5">
                  <Database className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <div className="font-semibold text-slate-200">PostgreSQL Full-Text Search</div>
                    <div className="text-[11px] text-slate-400">GIN Indexed (Tiers A-D)</div>
                  </div>
                </div>
                <Badge variant="success" size="sm">Active</Badge>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="flex items-center gap-2.5">
                  <Activity className="w-4 h-4 text-blue-400 shrink-0" />
                  <div>
                    <div className="font-semibold text-slate-200">Celery Async Workers</div>
                    <div className="text-[11px] text-slate-400">Redis Task Broker & Queue</div>
                  </div>
                </div>
                <Badge variant="success" size="sm">Ready</Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
