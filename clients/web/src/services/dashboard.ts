import { apiService } from './api'

export interface DashboardMetrics {
  totalRevenue: number
  previousRevenue: number
  newCustomers: number
  previousCustomers: number
  totalOrders: number
  previousOrders: number
  lowStockItems: number
  previousLowStock: number
  topProducts?: Array<{
    id: string
    name: string
    category: string
    sales: number
    revenue: number
    growth: number
    stock: number
    image?: string
  }>
  customerInsights?: {
    newCustomers: number
    returningCustomers: number
    activeCustomers: number
    churnRate: number
    customerLifetimeValue: number
    topCustomerSegments: Array<{
      segment: string
      count: number
      percentage: number
      value: number
    }>
    demographicBreakdown: Array<{
      name: string
      value: number
      color: string
    }>
  }
  alerts?: Array<{
    id: string
    message: string
    priority: 'low' | 'medium' | 'high'
    type: 'warning' | 'error' | 'info'
    timestamp: string
  }>
}

export interface SalesDataPoint {
  date: string
  revenue: number
  orders: number
  customers: number
}

export interface Activity {
  id: string
  type: 'user' | 'order' | 'inventory' | 'system' | 'chat'
  title: string
  description: string
  timestamp: string
  metadata?: {
    userId?: string
    orderId?: string
    amount?: number
    status?: string
    priority?: 'low' | 'medium' | 'high'
  }
}

export interface DashboardFilters {
  timeRange: '24h' | '7d' | '30d' | '90d' | '1y'
  dateFrom?: string
  dateTo?: string
  categories?: string[]
  segments?: string[]
}

class DashboardService {
  private readonly baseUrl = '/dashboard'

  async getMetrics(timeRange: string = '7d'): Promise<DashboardMetrics> {
    try {
      const response = await apiService.get<DashboardMetrics>(`${this.baseUrl}/metrics`, {
        params: { timeRange }
      })
      return response.data
    } catch (error) {
      console.error('Failed to fetch dashboard metrics:', error)
      // Return mock data for development
      return this.getMockMetrics()
    }
  }

  async getSalesData(timeRange: string = '7d'): Promise<SalesDataPoint[]> {
    try {
      const response = await apiService.get<SalesDataPoint[]>(`${this.baseUrl}/sales`, {
        params: { timeRange }
      })
      return response.data
    } catch (error) {
      console.error('Failed to fetch sales data:', error)
      return this.getMockSalesData()
    }
  }

  async getRecentActivity(limit: number = 10): Promise<Activity[]> {
    try {
      const response = await apiService.get<Activity[]>(`${this.baseUrl}/activity`, {
        params: { limit }
      })
      return response.data
    } catch (error) {
      console.error('Failed to fetch recent activity:', error)
      return this.getMockActivity()
    }
  }

  async getFilteredMetrics(filters: DashboardFilters): Promise<DashboardMetrics> {
    try {
      const response = await apiService.post<DashboardMetrics>(`${this.baseUrl}/metrics/filtered`, filters)
      return response.data
    } catch (error) {
      console.error('Failed to fetch filtered metrics:', error)
      return this.getMockMetrics()
    }
  }

  async exportData(format: 'csv' | 'xlsx' | 'pdf', filters?: DashboardFilters): Promise<void> {
    try {
      await apiService.downloadFile(
        `${this.baseUrl}/export/${format}`,
        `dashboard-export.${format}`
      )
    } catch (error) {
      console.error('Failed to export data:', error)
      throw error
    }
  }

  // Mock data for development/fallback
  private getMockMetrics(): DashboardMetrics {
    return {
      totalRevenue: 125000,
      previousRevenue: 98000,
      newCustomers: 145,
      previousCustomers: 132,
      totalOrders: 542,
      previousOrders: 489,
      lowStockItems: 12,
      previousLowStock: 8,
      topProducts: [
        {
          id: '1',
          name: 'Premium Wireless Headphones',
          category: 'Electronics',
          sales: 156,
          revenue: 24960,
          growth: 12.5,
          stock: 45,
        },
        {
          id: '2',
          name: 'Smart Fitness Tracker',
          category: 'Wearables',
          sales: 134,
          revenue: 20100,
          growth: 8.3,
          stock: 23,
        },
        {
          id: '3',
          name: 'Wireless Charging Pad',
          category: 'Accessories',
          sales: 89,
          revenue: 4450,
          growth: -2.1,
          stock: 67,
        },
        {
          id: '4',
          name: 'Bluetooth Speaker',
          category: 'Audio',
          sales: 76,
          revenue: 7600,
          growth: 15.7,
          stock: 8,
        },
        {
          id: '5',
          name: 'USB-C Cable',
          category: 'Accessories',
          sales: 198,
          revenue: 2970,
          growth: 5.2,
          stock: 156,
        },
      ],
      customerInsights: {
        newCustomers: 145,
        returningCustomers: 342,
        activeCustomers: 487,
        churnRate: 5.8,
        customerLifetimeValue: 850,
        topCustomerSegments: [
          {
            segment: 'Premium',
            count: 87,
            percentage: 17.9,
            value: 125000,
          },
          {
            segment: 'Regular',
            count: 234,
            percentage: 48.1,
            value: 78000,
          },
          {
            segment: 'New',
            count: 145,
            percentage: 29.8,
            value: 45000,
          },
        ],
        demographicBreakdown: [
          { name: 'Age 18-25', value: 125, color: '#3b82f6' },
          { name: 'Age 26-35', value: 189, color: '#10b981' },
          { name: 'Age 36-45', value: 134, color: '#f59e0b' },
          { name: 'Age 46+', value: 89, color: '#ef4444' },
        ],
      },
      alerts: [
        {
          id: '1',
          message: 'Inventory levels for Bluetooth Speaker are critically low',
          priority: 'high',
          type: 'warning',
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        },
        {
          id: '2',
          message: 'Customer satisfaction score dropped below threshold',
          priority: 'medium',
          type: 'warning',
          timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
        },
      ],
    }
  }

  private getMockSalesData(): SalesDataPoint[] {
    const data = []
    const now = new Date()
    
    for (let i = 6; i >= 0; i--) {
      const date = new Date(now)
      date.setDate(date.getDate() - i)
      
      data.push({
        date: date.toISOString(),
        revenue: Math.floor(Math.random() * 20000) + 10000,
        orders: Math.floor(Math.random() * 100) + 50,
        customers: Math.floor(Math.random() * 50) + 20,
      })
    }
    
    return data
  }

  private getMockActivity(): Activity[] {
    return [
      {
        id: '1',
        type: 'order',
        title: 'New order received',
        description: 'Order #12345 for Premium Wireless Headphones',
        timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
        metadata: {
          orderId: '12345',
          amount: 159.99,
          status: 'pending',
        },
      },
      {
        id: '2',
        type: 'user',
        title: 'New customer registered',
        description: 'John Doe joined as a new customer',
        timestamp: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
        metadata: {
          userId: 'user_001',
        },
      },
      {
        id: '3',
        type: 'inventory',
        title: 'Low stock alert',
        description: 'Bluetooth Speaker stock is below minimum threshold',
        timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
        metadata: {
          priority: 'high',
        },
      },
      {
        id: '4',
        type: 'chat',
        title: 'Customer inquiry',
        description: 'Customer asked about return policy',
        timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
        metadata: {
          userId: 'user_002',
        },
      },
      {
        id: '5',
        type: 'system',
        title: 'Backup completed',
        description: 'Daily backup process completed successfully',
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        metadata: {
          priority: 'low',
        },
      },
    ]
  }
}

export const dashboardService = new DashboardService()
export default dashboardService