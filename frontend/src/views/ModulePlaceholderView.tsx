import React from 'react'
import {
  Clock,
  Construction,
  FileCheck2,
  GitCompare,
  Search,
  UploadCloud,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import type { NavItemKey } from '@/components/layout/Sidebar'

interface ModuleInfo {
  title: string
  taskCode: string
  description: string
  deliverables: string[]
  icon: React.ReactNode
}

export const ModulePlaceholderView: React.FC<{ moduleKey: NavItemKey }> = ({ moduleKey }) => {
  const getModuleInfo = (key: NavItemKey): ModuleInfo => {
    switch (key) {
      case 'upload':
        return {
          title: 'Drag-and-Drop Batch Upload & Queue Monitor',
          taskCode: 'TASK-015',
          description:
            'High-throughput multi-format upload zone with client-side validation, Celery queue status polling, and real-time processing metrics.',
          deliverables: [
            'Multi-format file drop zone (PDF, PNG, JPG, TIFF, XLSX, XLS, CSV)',
            'Batch file queue table with per-document progress indicators',
            'Live Celery status polling (/api/documents/{id}/status/)',
            'Immediate error toast notifications and retry triggers',
          ],
          icon: <UploadCloud className="w-10 h-10 text-brand-400" />,
        }
      case 'review':
        return {
          title: 'Document Review & Side-by-Side Verification Workbench',
          taskCode: 'TASK-016',
          description:
            'Interactive inspection environment displaying source document text alongside structured invoice entities and validation findings.',
          deliverables: [
            'Dual-pane layout: source text viewer vs. structured fields',
            'Color-coded validation error badges with mathematical discrepancy indicators',
            'Itemized line items table with unit price and sum recalculations',
            'Extraction confidence scores and raw OCR evidence tooltips',
          ],
          icon: <FileCheck2 className="w-10 h-10 text-blue-400" />,
        }
      case 'reconcile':
        return {
          title: 'Cross-Document Reconciliation Workbench',
          taskCode: 'TASK-018',
          description:
            'Automated matching and dual-document discrepancy auditor connecting invoices with purchase orders and spreadsheet records.',
          deliverables: [
            'Dual-document selector with type filtering (PDF vs. PDF / PDF vs. Excel)',
            'Field-by-field variance matrix (totals, tax, line item counts)',
            'Audit discrepancy dismissal and justification workflow',
            'Full reconciliation log export and compliance history',
          ],
          icon: <GitCompare className="w-10 h-10 text-indigo-400" />,
        }
      case 'search':
        return {
          title: 'PostgreSQL Full-Text Search Interface',
          taskCode: 'TASK-018',
          description:
            'Unified search console leveraging the native PostgreSQL GIN index, 4-tier weighting hierarchy, and multi-word token query parser.',
          deliverables: [
            'Websearch syntax query parser (quotes, boolean OR, negation)',
            'Relevance-ranked results with match tier highlighting (A > B > C > D)',
            'Facet filtering by supplier, validation status, and date range',
            'Direct navigation from search hits into the Review Workbench',
          ],
          icon: <Search className="w-10 h-10 text-emerald-400" />,
        }
      default:
        return {
          title: 'Planned Module',
          taskCode: 'FUTURE-SPRINT',
          description: 'This operational module is scheduled for implementation in upcoming sprint phases.',
          deliverables: ['Feature development in progress'],
          icon: <Construction className="w-10 h-10 text-slate-400" />,
        }
    }
  }

  const info = getModuleInfo(moduleKey)

  return (
    <div className="max-w-4xl mx-auto space-y-6 py-6">
      <Card className="border-slate-800 bg-slate-900/60 p-8 text-center">
        <CardContent className="space-y-6 p-0 flex flex-col items-center">
          <div className="w-20 h-20 rounded-2xl bg-slate-800/80 border border-slate-700/80 flex items-center justify-center shadow-lg">
            {info.icon}
          </div>

          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold font-mono bg-brand-950/80 text-brand-300 border border-brand-800/80">
              <Clock className="w-3.5 h-3.5" />
              <span>{info.taskCode} Roadmap Target</span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-white">{info.title}</h2>
            <p className="text-sm text-slate-400 leading-relaxed">{info.description}</p>
          </div>

          <div className="w-full text-left bg-slate-950/60 border border-slate-800/80 rounded-xl p-5 mt-4">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">
              Planned Deliverables
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {info.deliverables.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-400 shrink-0 mt-1.5" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
