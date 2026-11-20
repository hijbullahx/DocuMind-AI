import React from 'react'

export interface ProgressBarProps {
  value: number
  size?: 'sm' | 'md' | 'lg'
  variant?: 'brand' | 'success' | 'warning' | 'danger'
  showLabel?: boolean
  animated?: boolean
  className?: string
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  size = 'sm',
  variant = 'brand',
  showLabel = false,
  animated = false,
  className = '',
}) => {
  const clampedValue = Math.min(100, Math.max(0, Math.round(value)))

  const heightStyles = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  }

  const variantStyles = {
    brand: 'bg-brand-500',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500',
  }

  return (
    <div className={`w-full flex items-center gap-2 ${className}`}>
      <div className={`flex-1 bg-slate-800 rounded-full overflow-hidden ${heightStyles[size]}`}>
        <div
          className={`h-full rounded-full transition-all duration-300 ease-out ${variantStyles[variant]} ${
            animated ? 'animate-pulse' : ''
          }`}
          style={{ width: `${clampedValue}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-[10px] font-mono text-slate-400 font-medium min-w-[32px] text-right">
          {clampedValue}%
        </span>
      )}
    </div>
  )
}
