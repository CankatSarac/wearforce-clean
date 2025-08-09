import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { Users, UserPlus, UserCheck, Crown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface CustomerInsight {
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

interface CustomerInsightsProps {
  insights?: CustomerInsight
}

const COLORS = {
  primary: 'hsl(var(--primary))',
  secondary: 'hsl(var(--chart-2))',
  tertiary: 'hsl(var(--chart-3))',
  quaternary: 'hsl(var(--chart-4))',
  accent: 'hsl(var(--accent))',
}

export function CustomerInsights({ insights }: CustomerInsightsProps) {
  if (!insights) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
        <Users className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No customer insights available</p>
      </div>
    )
  }

  const customerMetrics = [
    {
      label: 'New Customers',
      value: insights.newCustomers,
      icon: UserPlus,
      color: 'text-blue-600',
      bg: 'bg-blue-100 dark:bg-blue-900/20',
    },
    {
      label: 'Returning',
      value: insights.returningCustomers,
      icon: UserCheck,
      color: 'text-green-600',
      bg: 'bg-green-100 dark:bg-green-900/20',
    },
    {
      label: 'Active',
      value: insights.activeCustomers,
      icon: Users,
      color: 'text-purple-600',
      bg: 'bg-purple-100 dark:bg-purple-900/20',
    },
    {
      label: 'CLV',
      value: `$${insights.customerLifetimeValue.toFixed(0)}`,
      icon: Crown,
      color: 'text-yellow-600',
      bg: 'bg-yellow-100 dark:bg-yellow-900/20',
    },
  ]

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="rounded-lg border bg-background p-3 shadow-lg">
          <p className="font-medium">{data.name}</p>
          <p className="text-sm text-muted-foreground">
            Count: {data.value}
          </p>
          <p className="text-sm text-muted-foreground">
            Percentage: {((data.value / insights.demographicBreakdown.reduce((acc, item) => acc + item.value, 0)) * 100).toFixed(1)}%
          </p>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      {/* Customer Metrics Grid */}
      <div className="grid grid-cols-2 gap-3">
        {customerMetrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div
              key={metric.label}
              className={`p-3 rounded-lg ${metric.bg} border`}
            >
              <div className="flex items-center space-x-2">
                <Icon className={`h-4 w-4 ${metric.color}`} />
                <span className="text-xs font-medium text-muted-foreground">
                  {metric.label}
                </span>
              </div>
              <p className="text-lg font-bold mt-1">
                {typeof metric.value === 'string' ? metric.value : metric.value.toLocaleString()}
              </p>
            </div>
          )
        })}
      </div>

      {/* Churn Rate Alert */}
      {insights.churnRate > 10 && (
        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Users className="h-4 w-4 text-red-600" />
              <span className="text-sm font-medium text-red-800 dark:text-red-200">
                Churn Rate
              </span>
            </div>
            <Badge variant="destructive">
              {insights.churnRate.toFixed(1)}%
            </Badge>
          </div>
          <p className="text-xs text-red-700 dark:text-red-300 mt-1">
            Higher than recommended threshold
          </p>
        </div>
      )}

      {/* Top Customer Segments */}
      {insights.topCustomerSegments && insights.topCustomerSegments.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium">Top Customer Segments</h4>
          <div className="space-y-2">
            {insights.topCustomerSegments.slice(0, 3).map((segment, index) => (
              <div
                key={segment.segment}
                className="flex items-center justify-between p-2 rounded bg-muted/50"
              >
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                  <span className="text-sm font-medium">{segment.segment}</span>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium">{segment.count}</p>
                  <p className="text-xs text-muted-foreground">
                    {segment.percentage.toFixed(1)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Demographic Breakdown Chart */}
      {insights.demographicBreakdown && insights.demographicBreakdown.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium">Customer Demographics</h4>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={insights.demographicBreakdown}
                  cx="50%"
                  cy="50%"
                  innerRadius={30}
                  outerRadius={60}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {insights.demographicBreakdown.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.color || Object.values(COLORS)[index % Object.values(COLORS).length]} 
                    />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {insights.demographicBreakdown.slice(0, 4).map((item, index) => (
              <div key={item.name} className="flex items-center space-x-2">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ 
                    backgroundColor: item.color || Object.values(COLORS)[index % Object.values(COLORS).length] 
                  }}
                />
                <span className="truncate">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}