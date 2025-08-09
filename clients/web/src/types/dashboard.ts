export interface MetricTrend {
  value: number
  isPositive: boolean
  percentage: number
}

export interface ChartDataPoint {
  date: string
  value: number
  label?: string
  color?: string
}

export interface DashboardWidget {
  id: string
  title: string
  type: 'metric' | 'chart' | 'table' | 'activity' | 'custom'
  size: 'sm' | 'md' | 'lg' | 'xl'
  position: {
    x: number
    y: number
    w: number
    h: number
  }
  config: Record<string, any>
  visible: boolean
  refreshInterval?: number
}

export interface DashboardLayout {
  id: string
  name: string
  description?: string
  widgets: DashboardWidget[]
  isDefault: boolean
  createdAt: string
  updatedAt: string
}

export interface AlertConfig {
  id: string
  name: string
  metric: string
  condition: 'greater_than' | 'less_than' | 'equals' | 'not_equals'
  threshold: number
  enabled: boolean
  notifications: {
    email: boolean
    push: boolean
    slack?: boolean
  }
}

export interface DashboardPreferences {
  theme: 'light' | 'dark' | 'system'
  layout: string
  refreshInterval: number
  timezone: string
  currency: string
  dateFormat: string
  notifications: {
    desktop: boolean
    email: boolean
    sound: boolean
  }
  widgets: {
    showAnimations: boolean
    autoRefresh: boolean
    compactMode: boolean
  }
}