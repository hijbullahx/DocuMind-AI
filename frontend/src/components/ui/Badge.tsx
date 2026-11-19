import React from 'react'
import type { DocumentStatus, ValidationSeverity, ValidationStatus } from '@/types/document'

export type BadgeVariant =
  | DocumentStatus
  | ValidationStatus
  | ValidationSeverity
  | 'default'
  | 'neutral'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode
  variant?: BadgeVariant
  size?: 'sm' | 'md'
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className = '',
  ...props
}) => {
  const getVariantStyles = (v: BadgeVariant) => {
    switch (v) {
      case 'QUEUED':
        return 'bg-slate-800 text-slate-300 border-slate-700'
      case 'PROCESSING':
        return 'bg-blue-950/80 text-blue-300 border-blue-800/80 animate-pulse'
      case 'SUCCESS':
      case 'VERIFIED':
      case 'success':
        return 'bg-emerald-950/70 text-emerald-300 border-emerald-800/80'
      case 'NEEDS_REVIEW':
      case 'WARNING':
      case 'warning':
        return 'bg-amber-950/70 text-amber-300 border-amber-800/80'
      case 'FAILED':
      case 'ERROR':
      case 'danger':
        return 'bg-rose-950/70 text-rose-300 border-rose-800/80'
      case 'PARTIAL_SUCCESS':
      case 'INFO':
      case 'info':
        return 'bg-indigo-950/70 text-indigo-300 border-indigo-800/80'
      case 'PENDING':
        return 'bg-slate-800/80 text-slate-400 border-slate-700'
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700'
    }
  }

  const sizeStyles = {
    sm: 'text-[10px] px-2 py-0.5 font-medium',
    md: 'text-xs px-2.5 py-1 font-medium',
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border tracking-wide uppercase ${getVariantStyles(
        variant
      )} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            variant === 'PROCESSING'
              ? 'bg-blue-400 animate-ping'
              : variant === 'VERIFIED' || variant === 'SUCCESS'
              ? 'bg-emerald-400'
              : variant === 'NEEDS_REVIEW' || variant === 'WARNING'
              ? 'bg-amber-400'
              : variant === 'FAILED' || variant === 'ERROR'
              ? 'bg-rose-400'
              : 'bg-slate-400'
          }`}
        />
      )}
      <span>{children}</span>
    </span>
  )
}
