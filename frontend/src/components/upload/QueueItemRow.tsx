import React from 'react'
import {
  AlertCircle,
  FileSpreadsheet,
  FileText,
  Image,
  RefreshCw,
  X,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { ProgressBar } from '@/components/ui/ProgressBar'
import type { QueueItem } from '@/types/upload'

export interface QueueItemRowProps {
  item: QueueItem
  onRemove: (id: string) => void
  onRetry: (id: string) => void
}

export const QueueItemRow: React.FC<QueueItemRowProps> = ({ item, onRemove, onRetry }) => {
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  const getFileIcon = (ext: string) => {
    switch (ext.toLowerCase()) {
      case 'pdf':
        return <FileText className="w-4 h-4 text-rose-400 shrink-0" />
      case 'xlsx':
      case 'xls':
      case 'csv':
        return <FileSpreadsheet className="w-4 h-4 text-emerald-400 shrink-0" />
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'tiff':
      case 'tif':
        return <Image className="w-4 h-4 text-blue-400 shrink-0" />
      default:
        return <FileText className="w-4 h-4 text-slate-400 shrink-0" />
    }
  }

  return (
    <tr className="hover:bg-slate-800/40 transition-colors text-xs border-b border-slate-800/60">
      {/* File Info */}
      <td className="py-3 px-4 max-w-[240px]">
        <div className="flex items-center gap-2.5">
          {getFileIcon(item.fileType)}
          <div className="truncate">
            <div className="font-medium text-slate-200 truncate" title={item.filename}>
              {item.filename}
            </div>
            <div className="text-[11px] text-slate-400 font-mono">
              {formatBytes(item.fileSizeBytes)} • {item.fileType.toUpperCase()}
            </div>
          </div>
        </div>
      </td>

      {/* Upload Progress */}
      <td className="py-3 px-3 w-48">
        {item.clientStatus === 'UPLOADING' ? (
          <div className="space-y-1">
            <ProgressBar value={item.uploadProgress} size="sm" variant="brand" showLabel animated />
            <div className="text-[10px] text-brand-300">Uploading bytes...</div>
          </div>
        ) : item.clientStatus === 'PENDING' ? (
          <span className="text-[11px] text-slate-400 italic">Waiting for upload slot...</span>
        ) : item.clientStatus === 'FAILED' && !item.backendId ? (
          <span className="text-[11px] text-rose-400 font-medium">Upload failed</span>
        ) : (
          <div className="space-y-0.5">
            <ProgressBar value={100} size="sm" variant="success" />
            <span className="text-[10px] text-emerald-400 font-mono">100% Uploaded</span>
          </div>
        )}
      </td>

      {/* Pipeline Ingestion Status */}
      <td className="py-3 px-3 whitespace-nowrap">
        {item.clientStatus === 'PENDING' ? (
          <Badge variant="PENDING" size="sm">
            Pending
          </Badge>
        ) : item.clientStatus === 'UPLOADING' ? (
          <Badge variant="PROCESSING" size="sm" dot>
            Uploading
          </Badge>
        ) : item.backendStatus ? (
          <Badge variant={item.backendStatus} size="sm" dot={item.backendStatus === 'PROCESSING'}>
            {item.backendStatus}
          </Badge>
        ) : item.clientStatus === 'FAILED' ? (
          <Badge variant="FAILED" size="sm">
            Failed
          </Badge>
        ) : (
          <Badge variant="QUEUED" size="sm">
            Queued
          </Badge>
        )}
      </td>

      {/* Financial Validation Status */}
      <td className="py-3 px-3 whitespace-nowrap">
        {item.validationStatus ? (
          <Badge variant={item.validationStatus} size="sm">
            {item.validationStatus}
          </Badge>
        ) : (
          <span className="text-slate-400 text-[11px]">—</span>
        )}
      </td>

      {/* Diagnostics / Error Message */}
      <td className="py-3 px-3 max-w-[200px]">
        {item.errorMessage ? (
          <div
            className="flex items-center gap-1.5 text-rose-400 text-[11px] truncate cursor-help"
            title={item.errorMessage}
          >
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">{item.errorMessage}</span>
          </div>
        ) : item.clientStatus === 'SUCCESS' ? (
          <span className="text-emerald-400 text-[11px]">All rules passed clean</span>
        ) : item.clientStatus === 'NEEDS_REVIEW' ? (
          <span className="text-amber-400 text-[11px]">Review warnings flagged</span>
        ) : (
          <span className="text-slate-400 text-[11px]">—</span>
        )}
      </td>

      {/* Actions */}
      <td className="py-3 px-4 text-right whitespace-nowrap">
        <div className="flex items-center justify-end gap-1.5">
          {item.clientStatus === 'FAILED' && (
            <button
              onClick={() => onRetry(item.id)}
              className="p-1.5 rounded-lg text-amber-400 hover:text-amber-200 hover:bg-slate-800 transition-colors"
              title="Retry file upload or reprocessing"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}

          <button
            onClick={() => onRemove(item.id)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-300 hover:bg-slate-800 transition-colors"
            title="Remove from queue list"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </tr>
  )
}
