// Re-export commonly used formatting functions from lib/utils
export {
  formatCurrency,
  formatNumber,
  formatCompactNumber,
  formatPercent,
  formatDate,
  formatTime,
  formatDateTime,
  formatRelativeTime,
} from '@/lib/utils'

// Additional formatting utilities specific to business data
export function formatPercentageChange(current: number, previous: number): string {
  if (previous === 0) return '+0.0%'
  
  const change = ((current - previous) / previous) * 100
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(1)}%`
}

export function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`
}

export function formatDuration(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) return `${days}d ${hours % 24}h`
  if (hours > 0) return `${hours}h ${minutes % 60}m`
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`
  return `${seconds}s`
}

export function formatStatus(status: string): {
  label: string
  variant: 'default' | 'secondary' | 'destructive' | 'success' | 'warning'
} {
  const statusMap: Record<string, { label: string; variant: any }> = {
    active: { label: 'Active', variant: 'success' },
    inactive: { label: 'Inactive', variant: 'secondary' },
    pending: { label: 'Pending', variant: 'warning' },
    completed: { label: 'Completed', variant: 'success' },
    cancelled: { label: 'Cancelled', variant: 'destructive' },
    processing: { label: 'Processing', variant: 'warning' },
    shipped: { label: 'Shipped', variant: 'success' },
    delivered: { label: 'Delivered', variant: 'success' },
    failed: { label: 'Failed', variant: 'destructive' },
    draft: { label: 'Draft', variant: 'secondary' },
    published: { label: 'Published', variant: 'success' },
    archived: { label: 'Archived', variant: 'secondary' },
    deleted: { label: 'Deleted', variant: 'destructive' },
  }

  return statusMap[status.toLowerCase()] || { label: status, variant: 'default' }
}

export function formatPriority(priority: string): {
  label: string
  variant: 'default' | 'secondary' | 'destructive' | 'success' | 'warning'
  icon?: string
} {
  const priorityMap: Record<string, { label: string; variant: any; icon?: string }> = {
    low: { label: 'Low', variant: 'secondary', icon: '🟢' },
    medium: { label: 'Medium', variant: 'warning', icon: '🟡' },
    high: { label: 'High', variant: 'destructive', icon: '🔴' },
    urgent: { label: 'Urgent', variant: 'destructive', icon: '🚨' },
    critical: { label: 'Critical', variant: 'destructive', icon: '💀' },
  }

  return priorityMap[priority.toLowerCase()] || { label: priority, variant: 'default' }
}

export function formatBusinessHours(hours: number): string {
  if (hours === 0) return 'Closed'
  if (hours === 24) return '24 hours'
  
  const start = hours < 12 ? `${hours}:00 AM` : hours === 12 ? '12:00 PM' : `${hours - 12}:00 PM`
  const end = hours + 8 > 24 
    ? `${(hours + 8) - 24}:00 AM` 
    : hours + 8 === 12 
      ? '12:00 PM'
      : hours + 8 < 12
        ? `${hours + 8}:00 AM`
        : `${(hours + 8) - 12}:00 PM`
  
  return `${start} - ${end}`
}

export function formatPhoneNumber(phone: string, format: 'US' | 'international' = 'US'): string {
  const cleaned = phone.replace(/\D/g, '')
  
  if (format === 'US' && cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`
  }
  
  if (format === 'international') {
    if (cleaned.length === 11 && cleaned.startsWith('1')) {
      return `+1 (${cleaned.slice(1, 4)}) ${cleaned.slice(4, 7)}-${cleaned.slice(7)}`
    }
  }
  
  return phone
}

export function formatAddress(address: {
  street?: string
  city?: string
  state?: string
  zipCode?: string
  country?: string
}, multiline: boolean = false): string {
  const parts = []
  
  if (address.street) parts.push(address.street)
  
  const cityStateZip = [address.city, address.state, address.zipCode]
    .filter(Boolean)
    .join(', ')
  
  if (cityStateZip) parts.push(cityStateZip)
  if (address.country) parts.push(address.country)
  
  return multiline ? parts.join('\n') : parts.join(', ')
}

export function formatBusinessMetric(
  value: number,
  type: 'currency' | 'percentage' | 'count' | 'decimal',
  options?: {
    currency?: string
    locale?: string
    decimals?: number
    compact?: boolean
  }
): string {
  const { currency = 'USD', locale = 'en-US', decimals = 2, compact = false } = options || {}
  
  switch (type) {
    case 'currency':
      return compact && value >= 1000
        ? formatCurrency(value, currency, locale)
        : new Intl.NumberFormat(locale, {
            style: 'currency',
            currency,
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          }).format(value)
    
    case 'percentage':
      return new Intl.NumberFormat(locale, {
        style: 'percent',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(value / 100)
    
    case 'count':
      return compact 
        ? formatCompactNumber(value)
        : formatNumber(value, locale)
    
    case 'decimal':
      return new Intl.NumberFormat(locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(value)
    
    default:
      return value.toString()
  }
}