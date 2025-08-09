import { ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, ArrowUpDown, Mail, Phone, MapPin, Edit, Trash2, Eye } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
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
import { formatCurrency, getInitials, formatStatus } from '@/utils/format'

export interface Customer {
  id: string
  firstName: string
  lastName: string
  email: string
  phone?: string
  company?: string
  status: 'active' | 'inactive' | 'pending'
  customerType: 'individual' | 'business'
  totalOrders: number
  totalSpent: number
  lastOrderDate?: string
  createdAt: string
  updatedAt: string
  address?: {
    street: string
    city: string
    state: string
    zipCode: string
    country: string
  }
  tags?: string[]
  notes?: string
  avatar?: string
}

interface CustomersTableProps {
  data: Customer[]
  isLoading?: boolean
  error?: string | null
  onRefresh?: () => void
  onEdit?: (customer: Customer) => void
  onDelete?: (customer: Customer) => void
  onView?: (customer: Customer) => void
  onCreate?: () => void
}

export function CustomersTable({
  data,
  isLoading,
  error,
  onRefresh,
  onEdit,
  onDelete,
  onView,
  onCreate,
}: CustomersTableProps) {
  const columns: ColumnDef<Customer>[] = [
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
        const customer = row.original
        return (
          <div className="flex items-center space-x-3">
            <Avatar className="h-8 w-8">
              <AvatarImage src={customer.avatar} alt={`${customer.firstName} ${customer.lastName}`} />
              <AvatarFallback>
                {getInitials(`${customer.firstName} ${customer.lastName}`)}
              </AvatarFallback>
            </Avatar>
            <div>
              <div className="font-medium">
                {customer.firstName} {customer.lastName}
              </div>
              <div className="text-sm text-muted-foreground">
                {customer.email}
              </div>
            </div>
          </div>
        )
      },
      accessorFn: (row) => `${row.firstName} ${row.lastName}`,
      enableSorting: true,
    },
    {
      accessorKey: 'company',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Company
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => row.getValue('company') || 'Individual',
    },
    {
      accessorKey: 'customerType',
      header: 'Type',
      cell: ({ row }) => {
        const type = row.getValue('customerType') as string
        return (
          <Badge variant={type === 'business' ? 'default' : 'secondary'}>
            {type}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = row.getValue('status') as string
        const { label, variant } = formatStatus(status)
        return <Badge variant={variant}>{label}</Badge>
      },
    },
    {
      accessorKey: 'totalOrders',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Orders
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const orders = row.getValue('totalOrders') as number
        return <div className="text-right">{orders}</div>
      },
    },
    {
      accessorKey: 'totalSpent',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Total Spent
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const amount = row.getValue('totalSpent') as number
        return <div className="text-right font-medium">{formatCurrency(amount)}</div>
      },
    },
    {
      accessorKey: 'lastOrderDate',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Last Order
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const date = row.getValue('lastOrderDate') as string
        return date ? format(new Date(date), 'MMM dd, yyyy') : 'Never'
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
        return format(new Date(date), 'MMM dd, yyyy')
      },
    },
    {
      id: 'actions',
      enableHiding: false,
      cell: ({ row }) => {
        const customer = row.original

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
                <DropdownMenuItem onClick={() => onView(customer)}>
                  <Eye className="mr-2 h-4 w-4" />
                  View Details
                </DropdownMenuItem>
              )}
              {onEdit && (
                <DropdownMenuItem onClick={() => onEdit(customer)}>
                  <Edit className="mr-2 h-4 w-4" />
                  Edit Customer
                </DropdownMenuItem>
              )}
              <DropdownMenuItem 
                onClick={() => navigator.clipboard.writeText(customer.email)}
              >
                <Mail className="mr-2 h-4 w-4" />
                Copy Email
              </DropdownMenuItem>
              {customer.phone && (
                <DropdownMenuItem 
                  onClick={() => navigator.clipboard.writeText(customer.phone!)}
                >
                  <Phone className="mr-2 h-4 w-4" />
                  Copy Phone
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              {onDelete && (
                <DropdownMenuItem 
                  onClick={() => onDelete(customer)}
                  className="text-destructive"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Customer
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
      title="Customers"
      description="Manage your customer database and relationships"
      searchKey="customers"
      isLoading={isLoading}
      error={error}
      onRefresh={onRefresh}
      onCreate={onCreate}
      showExport
      showSearch
      showFilter
      showCreate
      showPagination
      pageSize={25}
    />
  )
}