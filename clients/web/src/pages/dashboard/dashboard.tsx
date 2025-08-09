import { useEffect } from 'react'
import {
  BarChart3,
  Users,
  ShoppingCart,
  Package,
  TrendingUp,
  TrendingDown,
  DollarSign,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { MetricCard } from '@/components/dashboard/metric-card'
import { SalesChart } from '@/components/dashboard/sales-chart'
import { RecentActivities } from '@/components/dashboard/recent-activities'
import { TopProducts } from '@/components/dashboard/top-products'
import { CustomerInsights } from '@/components/dashboard/customer-insights'
import { QuickActions } from '@/components/dashboard/quick-actions'

import { useAuth } from '@/hooks/useAuth'
import { useDashboardStore } from '@/store/dashboard-store'
import { formatCurrency, formatNumber } from '@/utils/format'

export function DashboardPage() {
  const { user } = useAuth()
  const {
    metrics,
    salesData,
    activities,
    isLoading,
    error,
    selectedTimeRange,
    setTimeRange,
    refreshData,
    clearError,
  } = useDashboardStore()

  // Load data on component mount and time range change
  useEffect(() => {
    refreshData()
  }, [selectedTimeRange, refreshData])

  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 17) return 'Good afternoon'
    return 'Good evening'
  }

  const getMetricTrend = (current: number, previous: number) => {
    if (previous === 0) return { value: 0, isPositive: true }
    const change = ((current - previous) / previous) * 100
    return { value: Math.abs(change), isPositive: change >= 0 }
  }

  const handleRefresh = () => {
    clearError()
    refreshData()
  }

  if (isLoading && !metrics) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <div className="h-8 w-64 bg-muted animate-pulse rounded" />
          <div className="h-5 w-48 bg-muted animate-pulse rounded" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 h-96 bg-muted animate-pulse rounded-lg" />
          <div className="h-96 bg-muted animate-pulse rounded-lg" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <div className="text-center space-y-2">
          <h2 className="text-lg font-semibold">Failed to load dashboard</h2>
          <p className="text-sm text-muted-foreground max-w-md">{error}</p>
        </div>
        <Button onClick={handleRefresh} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col space-y-2 lg:flex-row lg:items-center lg:justify-between lg:space-y-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {getGreeting()}, {user?.firstName}!
          </h1>
          <p className="text-muted-foreground">
            Here's what's happening with your business today.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoading}
            className="mr-2"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Tabs value={selectedTimeRange} onValueChange={setTimeRange}>
            <TabsList>
              <TabsTrigger value="24h">24h</TabsTrigger>
              <TabsTrigger value="7d">7d</TabsTrigger>
              <TabsTrigger value="30d">30d</TabsTrigger>
              <TabsTrigger value="90d">90d</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Revenue"
          value={formatCurrency(metrics?.totalRevenue || 0)}
          change={getMetricTrend(
            metrics?.totalRevenue || 0,
            metrics?.previousRevenue || 0
          )}
          icon={DollarSign}
        />
        <MetricCard
          title="New Customers"
          value={formatNumber(metrics?.newCustomers || 0)}
          change={getMetricTrend(
            metrics?.newCustomers || 0,
            metrics?.previousCustomers || 0
          )}
          icon={Users}
        />
        <MetricCard
          title="Orders"
          value={formatNumber(metrics?.totalOrders || 0)}
          change={getMetricTrend(
            metrics?.totalOrders || 0,
            metrics?.previousOrders || 0
          )}
          icon={ShoppingCart}
        />
        <MetricCard
          title="Low Stock Items"
          value={formatNumber(metrics?.lowStockItems || 0)}
          change={getMetricTrend(
            metrics?.lowStockItems || 0,
            metrics?.previousLowStock || 0
          )}
          icon={Package}
          variant={metrics?.lowStockItems > 0 ? "warning" : "default"}
        />
      </div>

      {/* Charts and Insights */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Sales Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Sales Overview</CardTitle>
            <CardDescription>
              Revenue and orders over the selected period
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SalesChart data={salesData} />
          </CardContent>
        </Card>

        {/* Recent Activities */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activities</CardTitle>
            <CardDescription>Latest updates from your team</CardDescription>
          </CardHeader>
          <CardContent>
            <RecentActivities activities={activities?.slice(0, 5)} />
          </CardContent>
        </Card>
      </div>

      {/* Secondary Content */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Top Products */}
        <Card>
          <CardHeader>
            <CardTitle>Top Products</CardTitle>
            <CardDescription>Best performing items this period</CardDescription>
          </CardHeader>
          <CardContent>
            <TopProducts products={metrics?.topProducts} />
          </CardContent>
        </Card>

        {/* Customer Insights */}
        <Card>
          <CardHeader>
            <CardTitle>Customer Insights</CardTitle>
            <CardDescription>Key customer metrics and trends</CardDescription>
          </CardHeader>
          <CardContent>
            <CustomerInsights insights={metrics?.customerInsights} />
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks and shortcuts</CardDescription>
          </CardHeader>
          <CardContent>
            <QuickActions />
          </CardContent>
        </Card>
      </div>

      {/* Alerts and Notifications */}
      {metrics?.alerts && metrics.alerts.length > 0 && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              Attention Required
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {metrics.alerts.map((alert, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-destructive/10 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="destructive">{alert.priority}</Badge>
                    <span className="text-sm">{alert.message}</span>
                  </div>
                  <Button variant="outline" size="sm">
                    View
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}