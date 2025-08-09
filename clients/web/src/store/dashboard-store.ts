import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { subscribeWithSelector } from 'zustand/middleware'
import { DashboardMetrics, SalesDataPoint, Activity } from '@/services/dashboard'
import { DashboardLayout, DashboardPreferences } from '@/types/dashboard'

interface DashboardStore {
  // Data
  metrics: DashboardMetrics | null
  salesData: SalesDataPoint[]
  activities: Activity[]
  isLoading: boolean
  error: string | null
  lastUpdated: Date | null

  // UI State
  selectedTimeRange: '24h' | '7d' | '30d' | '90d' | '1y'
  currentLayout: DashboardLayout | null
  preferences: DashboardPreferences
  sidebarCollapsed: boolean
  
  // Actions
  setMetrics: (metrics: DashboardMetrics) => void
  setSalesData: (data: SalesDataPoint[]) => void
  setActivities: (activities: Activity[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setTimeRange: (range: '24h' | '7d' | '30d' | '90d' | '1y') => void
  setCurrentLayout: (layout: DashboardLayout | null) => void
  updatePreferences: (preferences: Partial<DashboardPreferences>) => void
  setSidebarCollapsed: (collapsed: boolean) => void
  refreshData: () => Promise<void>
  clearError: () => void
}

const defaultPreferences: DashboardPreferences = {
  theme: 'system',
  layout: 'default',
  refreshInterval: 30000, // 30 seconds
  timezone: 'UTC',
  currency: 'USD',
  dateFormat: 'MM/dd/yyyy',
  notifications: {
    desktop: true,
    email: false,
    sound: false,
  },
  widgets: {
    showAnimations: true,
    autoRefresh: true,
    compactMode: false,
  },
}

export const useDashboardStore = create<DashboardStore>()(
  subscribeWithSelector(
    immer((set, get) => ({
      // Initial state
      metrics: null,
      salesData: [],
      activities: [],
      isLoading: false,
      error: null,
      lastUpdated: null,
      selectedTimeRange: '7d',
      currentLayout: null,
      preferences: defaultPreferences,
      sidebarCollapsed: false,

      // Actions
      setMetrics: (metrics) =>
        set((state) => {
          state.metrics = metrics
          state.lastUpdated = new Date()
          state.error = null
        }),

      setSalesData: (data) =>
        set((state) => {
          state.salesData = data
        }),

      setActivities: (activities) =>
        set((state) => {
          state.activities = activities
        }),

      setLoading: (loading) =>
        set((state) => {
          state.isLoading = loading
        }),

      setError: (error) =>
        set((state) => {
          state.error = error
          state.isLoading = false
        }),

      setTimeRange: (range) =>
        set((state) => {
          state.selectedTimeRange = range
        }),

      setCurrentLayout: (layout) =>
        set((state) => {
          state.currentLayout = layout
        }),

      updatePreferences: (newPreferences) =>
        set((state) => {
          state.preferences = { ...state.preferences, ...newPreferences }
          // Persist to localStorage
          localStorage.setItem('dashboard-preferences', JSON.stringify(state.preferences))
        }),

      setSidebarCollapsed: (collapsed) =>
        set((state) => {
          state.sidebarCollapsed = collapsed
          localStorage.setItem('sidebar-collapsed', JSON.stringify(collapsed))
        }),

      refreshData: async () => {
        const { setLoading, setError, setMetrics, setSalesData, setActivities, selectedTimeRange } = get()
        
        setLoading(true)
        setError(null)
        
        try {
          // Import services dynamically to avoid circular dependencies
          const { dashboardService } = await import('@/services/dashboard')
          
          const [metrics, salesData, activities] = await Promise.all([
            dashboardService.getMetrics(selectedTimeRange),
            dashboardService.getSalesData(selectedTimeRange),
            dashboardService.getRecentActivity(10),
          ])
          
          setMetrics(metrics)
          setSalesData(salesData)
          setActivities(activities)
        } catch (error) {
          console.error('Failed to refresh dashboard data:', error)
          setError(error instanceof Error ? error.message : 'Failed to refresh data')
        } finally {
          setLoading(false)
        }
      },

      clearError: () =>
        set((state) => {
          state.error = null
        }),
    }))
  )
)

// Selectors for computed values
export const useDashboardMetrics = () => useDashboardStore((state) => state.metrics)
export const useSalesData = () => useDashboardStore((state) => state.salesData)
export const useActivities = () => useDashboardStore((state) => state.activities)
export const useDashboardLoading = () => useDashboardStore((state) => state.isLoading)
export const useDashboardError = () => useDashboardStore((state) => state.error)
export const useTimeRange = () => useDashboardStore((state) => state.selectedTimeRange)
export const useDashboardPreferences = () => useDashboardStore((state) => state.preferences)

// Initialize store from localStorage
if (typeof window !== 'undefined') {
  // Load preferences
  const savedPreferences = localStorage.getItem('dashboard-preferences')
  if (savedPreferences) {
    try {
      const preferences = JSON.parse(savedPreferences)
      useDashboardStore.getState().updatePreferences(preferences)
    } catch (error) {
      console.warn('Failed to load dashboard preferences:', error)
    }
  }

  // Load sidebar state
  const savedSidebarState = localStorage.getItem('sidebar-collapsed')
  if (savedSidebarState) {
    try {
      const collapsed = JSON.parse(savedSidebarState)
      useDashboardStore.getState().setSidebarCollapsed(collapsed)
    } catch (error) {
      console.warn('Failed to load sidebar state:', error)
    }
  }
}

// Auto-refresh setup
let refreshInterval: NodeJS.Timeout | null = null

useDashboardStore.subscribe(
  (state) => state.preferences.widgets.autoRefresh,
  (autoRefresh) => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }

    if (autoRefresh) {
      const interval = useDashboardStore.getState().preferences.refreshInterval
      refreshInterval = setInterval(() => {
        useDashboardStore.getState().refreshData()
      }, interval)
    }
  }
)

// Clean up on unmount
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
    }
  })
}