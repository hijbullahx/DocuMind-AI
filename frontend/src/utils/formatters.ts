/**
 * Formatting and mathematical comparison utilities for Document Intelligence & Review Workbench.
 */

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return '0 B'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return '—'
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export function formatCurrency(
  amount: number | string | null | undefined,
  currency?: string | null
): string {
  if (amount === null || amount === undefined || amount === '') return '—'

  const num = typeof amount === 'number' ? amount : parseFloat(String(amount).replace(/[^0-9.-]/g, ''))
  if (isNaN(num)) return String(amount)

  const formattedNum = num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  const curr = (currency || '').trim().toUpperCase()
  if (!curr || curr === '$' || curr === 'USD') {
    return `$${formattedNum}`
  }
  if (curr === '€' || curr === 'EUR') {
    return `€${formattedNum}`
  }
  if (curr === '£' || curr === 'GBP') {
    return `£${formattedNum}`
  }
  return `${curr} ${formattedNum}`
}

export function formatConfidence(score: number | null | undefined): {
  percentage: number
  label: string
  variant: 'success' | 'warning' | 'danger'
} {
  if (score === null || score === undefined || isNaN(score)) {
    return { percentage: 0, label: 'N/A', variant: 'warning' }
  }

  // Model score can be 0.0-1.0 or 0-100
  const normalized = score <= 1.0 && score > 0 ? Math.round(score * 100) : Math.round(score)
  const clamped = Math.max(0, Math.min(100, normalized))

  if (clamped >= 85) {
    return { percentage: clamped, label: `${clamped}%`, variant: 'success' }
  } else if (clamped >= 60) {
    return { percentage: clamped, label: `${clamped}%`, variant: 'warning' }
  }
  return { percentage: clamped, label: `${clamped}%`, variant: 'danger' }
}

export function checkMathEquality(
  val1: number | null | undefined,
  val2: number | null | undefined,
  tolerance = 0.05
): { diff: number; matches: boolean } {
  if (val1 === null || val1 === undefined || val2 === null || val2 === undefined) {
    return { diff: 0, matches: false }
  }
  const diff = Math.round((val1 - val2) * 10000) / 10000
  return {
    diff,
    matches: Math.abs(diff) <= tolerance,
  }
}
