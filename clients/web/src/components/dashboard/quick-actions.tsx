import { 
  Plus, 
  UserPlus, 
  ShoppingCart, 
  Package, 
  FileText, 
  MessageSquare,
  BarChart3,
  Settings,
  Download,
  Upload
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useNavigate } from 'react-router-dom'

interface QuickAction {
  id: string
  label: string
  icon: React.ElementType
  href?: string
  onClick?: () => void
  variant?: 'default' | 'outline' | 'secondary'
  disabled?: boolean
}

export function QuickActions() {
  const navigate = useNavigate()

  const quickActions: QuickAction[] = [
    {
      id: 'new-order',
      label: 'New Order',
      icon: Plus,
      href: '/erp/orders/new',
      variant: 'default',
    },
    {
      id: 'add-customer',
      label: 'Add Customer',
      icon: UserPlus,
      href: '/crm/customers/new',
      variant: 'outline',
    },
    {
      id: 'manage-inventory',
      label: 'Inventory',
      icon: Package,
      href: '/erp/inventory',
      variant: 'outline',
    },
    {
      id: 'view-analytics',
      label: 'Analytics',
      icon: BarChart3,
      href: '/analytics',
      variant: 'outline',
    },
    {
      id: 'start-chat',
      label: 'AI Assistant',
      icon: MessageSquare,
      href: '/chat',
      variant: 'secondary',
    },
    {
      id: 'generate-report',
      label: 'Generate Report',
      icon: FileText,
      onClick: () => handleGenerateReport(),
      variant: 'outline',
    },
    {
      id: 'export-data',
      label: 'Export Data',
      icon: Download,
      onClick: () => handleExportData(),
      variant: 'outline',
    },
    {
      id: 'import-data',
      label: 'Import Data',
      icon: Upload,
      onClick: () => handleImportData(),
      variant: 'outline',
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      href: '/settings',
      variant: 'outline',
    },
  ]

  const handleAction = (action: QuickAction) => {
    if (action.onClick) {
      action.onClick()
    } else if (action.href) {
      navigate(action.href)
    }
  }

  const handleGenerateReport = () => {
    // TODO: Implement report generation
    console.log('Generate report clicked')
  }

  const handleExportData = () => {
    // TODO: Implement data export
    console.log('Export data clicked')
  }

  const handleImportData = () => {
    // TODO: Implement data import
    console.log('Import data clicked')
  }

  return (
    <div className="space-y-4">
      {/* Primary Actions */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-muted-foreground">Quick Actions</h4>
        <div className="grid grid-cols-1 gap-2">
          {quickActions.slice(0, 3).map((action) => {
            const Icon = action.icon
            return (
              <Button
                key={action.id}
                variant={action.variant}
                size="sm"
                className="justify-start"
                onClick={() => handleAction(action)}
                disabled={action.disabled}
              >
                <Icon className="h-4 w-4 mr-2" />
                {action.label}
              </Button>
            )
          })}
        </div>
      </div>

      {/* Secondary Actions */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-muted-foreground">Tools</h4>
        <div className="grid grid-cols-2 gap-2">
          {quickActions.slice(3, 7).map((action) => {
            const Icon = action.icon
            return (
              <Button
                key={action.id}
                variant={action.variant}
                size="sm"
                className="justify-start"
                onClick={() => handleAction(action)}
                disabled={action.disabled}
              >
                <Icon className="h-4 w-4 mr-2" />
                <span className="truncate">{action.label}</span>
              </Button>
            )
          })}
        </div>
      </div>

      {/* Utilities */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-muted-foreground">Utilities</h4>
        <div className="grid grid-cols-1 gap-2">
          {quickActions.slice(7).map((action) => {
            const Icon = action.icon
            return (
              <Button
                key={action.id}
                variant={action.variant}
                size="sm"
                className="justify-start"
                onClick={() => handleAction(action)}
                disabled={action.disabled}
              >
                <Icon className="h-4 w-4 mr-2" />
                {action.label}
              </Button>
            )
          })}
        </div>
      </div>

      {/* Help Section */}
      <div className="pt-4 border-t">
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-muted-foreground">Need Help?</h4>
          <div className="text-xs text-muted-foreground">
            <p>Use the AI Assistant to get help with any task</p>
            <Button
              variant="link"
              size="sm"
              className="h-auto p-0 text-xs"
              onClick={() => navigate('/chat')}
            >
              Start a conversation →
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}