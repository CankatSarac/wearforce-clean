import { ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, ArrowUpDown, Package, Truck, CheckCircle, XCircle, Clock } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Checkbox } from '@/components/ui/checkbox'
import { DataTable } from './data-table'
import { formatCurrency, formatStatus } from '@/utils/format'

export interface Order {
  id: string
  orderNumber: string
  customerId: string
  customerName: string
  customerEmail: string
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled' | 'returned'
  paymentStatus: 'pending' | 'paid' | 'failed' | 'refunded'
  total: number
  subtotal: number
  tax: number
  shipping: number
  discount?: number
  currency: string
  items: Array<{
    id: string
    name: string
    quantity: number
    price: number
    sku: string
  }>
  shippingAddress: {
    street: string
    city: string
    state: string
    zipCode: string
    country: string
  }
  trackingNumber?: string
  notes?: string
  createdAt: string
  updatedAt: string
  shippedAt?: string
  deliveredAt?: string
}

interface OrdersTableProps {
  data: Order[]
  isLoading?: boolean
  error?: string | null
  onRefresh?: () => void
  onEdit?: (order: Order) => void
  onCancel?: (order: Order) => void
  onView?: (order: Order) => void
  onCreate?: () => void
  onUpdateStatus?: (order: Order, status: Order['status']) => void
}

export function OrdersTable({
  data,
  isLoading,
  error,
  onRefresh,
  onEdit,
  onCancel,
  onView,
  onCreate,
  onUpdateStatus,
}: OrdersTableProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4" />
      case 'processing':
        return <Package className="h-4 w-4" />
      case 'shipped':
        return <Truck className="h-4 w-4" />
      case 'delivered':
        return <CheckCircle className="h-4 w-4" />
      case 'cancelled':
      case 'returned':
        return <XCircle className="h-4 w-4" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  const getPaymentStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return 'success'
      case 'pending':
        return 'warning'
      case 'failed':
        return 'destructive'
      case 'refunded':
        return 'secondary'
      default:
        return 'secondary'
    }
  }

  const columns: ColumnDef<Order>[] = [
    {
      id: 'select',
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: 'orderNumber',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Order #
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const orderNumber = row.getValue('orderNumber') as string
        return (
          <div className="font-mono text-sm font-medium">
            {orderNumber}
          </div>
        )
      },
    },
    {
      id: 'customer',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Customer
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const order = row.original
        return (
          <div>
            <div className="font-medium">{order.customerName}</div>
            <div className="text-sm text-muted-foreground">{order.customerEmail}</div>
          </div>
        )
      },
      accessorFn: (row) => row.customerName,
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = row.getValue('status') as string
        const { label, variant } = formatStatus(status)
        return (
          <div className="flex items-center space-x-2">
            {getStatusIcon(status)}
            <Badge variant={variant}>{label}</Badge>
          </div>
        )
      },
    },
    {
      accessorKey: 'paymentStatus',
      header: 'Payment',
      cell: ({ row }) => {
        const status = row.getValue('paymentStatus') as string
        return (
          <Badge variant={getPaymentStatusColor(status) as any}>
            {status}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'total',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Total
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const amount = row.getValue('total') as number
        const currency = row.original.currency
        return (
          <div className="text-right font-medium">
            {formatCurrency(amount, currency)}
          </div>
        )
      },
    },
    {
      id: 'items',
      header: 'Items',
      cell: ({ row }) => {
        const items = row.original.items
        const totalQuantity = items.reduce((sum, item) => sum + item.quantity, 0)
        return (
          <div className="text-right">
            <div className="font-medium">{totalQuantity} items</div>
            <div className="text-sm text-muted-foreground">
              {items.length} product{items.length > 1 ? 's' : ''}
            </div>
          </div>
        )
      },
    },
    {
      accessorKey: 'createdAt',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Created
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const date = row.getValue('createdAt') as string
        return (
          <div>
            <div>{format(new Date(date), 'MMM dd, yyyy')}</div>
            <div className="text-sm text-muted-foreground">
              {format(new Date(date), 'HH:mm')}
            </div>
          </div>
        )
      },
    },
    {
      accessorKey: 'trackingNumber',
      header: 'Tracking',
      cell: ({ row }) => {
        const trackingNumber = row.getValue('trackingNumber') as string
        return trackingNumber ? (
          <div className="font-mono text-sm">{trackingNumber}</div>
        ) : (
          <div className="text-sm text-muted-foreground">Not shipped</div>
        )
      },
    },
    {
      id: 'actions',
      enableHiding: false,
      cell: ({ row }) => {
        const order = row.original

        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {onView && (
                <DropdownMenuItem onClick={() => onView(order)}>
                  View Order Details
                </DropdownMenuItem>
              )}
              {onEdit && (
                <DropdownMenuItem onClick={() => onEdit(order)}>
                  Edit Order
                </DropdownMenuItem>
              )}
              <DropdownMenuItem
                onClick={() => navigator.clipboard.writeText(order.orderNumber)}
              >
                Copy Order Number
              </DropdownMenuItem>
              {order.trackingNumber && (
                <DropdownMenuItem
                  onClick={() => navigator.clipboard.writeText(order.trackingNumber!)}
                >
                  Copy Tracking Number
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              
              {/* Status update options */}
              {onUpdateStatus && order.status !== 'delivered' && order.status !== 'cancelled' && (
                <>
                  <DropdownMenuLabel>Update Status</DropdownMenuLabel>
                  {order.status === 'pending' && (
                    <DropdownMenuItem onClick={() => onUpdateStatus(order, 'processing')}>
                      Mark as Processing
                    </DropdownMenuItem>
                  )}
                  {order.status === 'processing' && (
                    <DropdownMenuItem onClick={() => onUpdateStatus(order, 'shipped')}>
                      Mark as Shipped
                    </DropdownMenuItem>
                  )}
                  {order.status === 'shipped' && (
                    <DropdownMenuItem onClick={() => onUpdateStatus(order, 'delivered')}>
                      Mark as Delivered
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                </>
              )}
              
              {onCancel && order.status !== 'cancelled' && order.status !== 'delivered' && (
                <DropdownMenuItem
                  onClick={() => onCancel(order)}
                  className="text-destructive"
                >
                  Cancel Order
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]

  return (
    <DataTable
      columns={columns}
      data={data}
      title="Orders"
      description="Manage customer orders and fulfillment"
      searchKey="orders"
      isLoading={isLoading}
      error={error}
      onRefresh={onRefresh}
      onCreate={onCreate}
      showExport
      showSearch
      showFilter
      showCreate
      showPagination
      pageSize={20}
    />
  )
}