import React, { useRef, useState } from 'react'
import { FileUp, HardDriveUpload, UploadCloud } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export interface DropzoneProps {
  onFilesSelected: (files: FileList | File[]) => void
  disabled?: boolean
}

export const Dropzone: React.FC<DropzoneProps> = ({ onFilesSelected, disabled = false }) => {
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled && !isDragOver) setIsDragOver(true)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    if (disabled) return
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesSelected(e.dataTransfer.files)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(e.target.files)
      // Reset input value so same files can be re-selected if removed
      e.target.value = ''
    }
  }

  return (
    <div
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 text-center p-8 sm:p-10 flex flex-col items-center justify-center gap-4 ${
        isDragOver
          ? 'border-brand-400 bg-brand-950/40 shadow-xl shadow-brand-500/10 scale-[1.01]'
          : 'border-slate-800 hover:border-slate-700 bg-slate-900/60 hover:bg-slate-900/90'
      } ${disabled ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}`}
      onClick={() => fileInputRef.current?.click()}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.xlsx,.xls,.csv,.txt"
        className="hidden"
        onChange={handleFileInputChange}
        disabled={disabled}
      />

      <div
        className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-all shadow-md ${
          isDragOver
            ? 'bg-brand-600 text-white shadow-brand-500/30 rotate-3'
            : 'bg-slate-800 text-brand-400 border border-slate-700 group-hover:scale-105'
        }`}
      >
        {isDragOver ? (
          <HardDriveUpload className="w-8 h-8 animate-bounce" />
        ) : (
          <UploadCloud className="w-8 h-8" />
        )}
      </div>

      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base font-semibold text-white tracking-tight">
          {isDragOver ? 'Drop files to queue for processing' : 'Drag & drop documents here, or browse'}
        </h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          Supports multi-format invoices, receipts, and spreadsheets for OCR, structured AI extraction, and math validation.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-1.5 max-w-lg mt-1">
        {['PDF', 'PNG', 'JPG', 'TIFF', 'XLSX', 'XLS', 'CSV', 'TXT'].map((ext) => (
          <span
            key={ext}
            className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800/80 text-slate-300 border border-slate-700/80"
          >
            {ext}
          </span>
        ))}
        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-brand-950 text-brand-300 border border-brand-800/80">
          Max 25 MB per file
        </span>
      </div>

      <div className="pt-2">
        <Button
          type="button"
          variant="primary"
          size="md"
          leftIcon={<FileUp className="w-4 h-4" />}
          onClick={(e) => {
            e.stopPropagation()
            fileInputRef.current?.click()
          }}
          disabled={disabled}
        >
          Select Files to Upload
        </Button>
      </div>
    </div>
  )
}
