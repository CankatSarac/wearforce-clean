import { formatDistanceToNow } from 'date-fns'
import { 
  User, 
  ShoppingCart, 
  Package, 
  TrendingUp, 
  AlertCircle, 
  CheckCircle,
  Clock,
  MessageSquare
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'

interface Activity {
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

interface RecentActivitiesProps {
  activities?: Activity[]
  limit?: number
}

export function RecentActivities({ activities = [], limit = 10 }: RecentActivitiesProps) {
  const displayActivities = activities.slice(0, limit)

  const getActivityIcon = (type: string, status?: string) => {
    switch (type) {
      case 'user':
        return <User className="h-4 w-4 text-blue-500" />
      case 'order':
        return status === 'completed' ? 
          <CheckCircle className="h-4 w-4 text-green-500" /> :
          <ShoppingCart className="h-4 w-4 text-orange-500" />
      case 'inventory':
        return <Package className="h-4 w-4 text-purple-500" />
      case 'system':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'chat':
        return <MessageSquare className="h-4 w-4 text-cyan-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  const getPriorityBadge = (priority?: string) => {
    if (!priority) return null
    
    const variants = {
      low: 'secondary',
      medium: 'warning',
      high: 'destructive',
    } as const

    return (
      <Badge variant={variants[priority as keyof typeof variants]} size="sm">
        {priority}
      </Badge>
    )
  }

  if (displayActivities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
        <Clock className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No recent activities</p>
      </div>
    )
  }

  return (
    <ScrollArea className="h-[400px]">
      <div className="space-y-4">
        {displayActivities.map((activity) => (
          <div
            key={activity.id}
            className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
          >
            <div className="flex-shrink-0 mt-0.5">
              {getActivityIcon(activity.type, activity.metadata?.status)}
            </div>
            
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-foreground truncate">
                  {activity.title}
                </p>
                <div className="flex items-center space-x-2">
                  {getPriorityBadge(activity.metadata?.priority)}
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatDistanceToNow(new Date(activity.timestamp), { addSuffix: true })}
                  </span>
                </div>
              </div>
              
              <p className="text-xs text-muted-foreground line-clamp-2">
                {activity.description}
              </p>
              
              {activity.metadata && (
                <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                  {activity.metadata.userId && (
                    <span>User: {activity.metadata.userId}</span>
                  )}
                  {activity.metadata.orderId && (
                    <span>Order: #{activity.metadata.orderId}</span>
                  )}
                  {activity.metadata.amount && (
                    <span className="text-green-600 font-medium">
                      ${activity.metadata.amount.toFixed(2)}
                    </span>
                  )}
                  {activity.metadata.status && (
                    <Badge variant="outline" className="text-xs py-0">
                      {activity.metadata.status}
                    </Badge>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}