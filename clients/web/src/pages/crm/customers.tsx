import { useState, useEffect } from 'react'
import { CustomersTable, type Customer } from '@/components/tables/customers-table'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

// Mock data for development
const mockCustomers: Customer[] = [
  {
    id: '1',
    firstName: 'John',
    lastName: 'Doe',
    email: 'john.doe@example.com',
    phone: '+1 (555) 123-4567',
    company: 'Tech Solutions Inc.',
    status: 'active',
    customerType: 'business',
    totalOrders: 15,
    totalSpent: 12450.00,
    lastOrderDate: '2024-01-15T10:30:00Z',
    createdAt: '2023-06-15T09:00:00Z',
    updatedAt: '2024-01-15T10:30:00Z',
    address: {
      street: '123 Business Ave',
      city: 'San Francisco',
      state: 'CA',
      zipCode: '94105',
      country: 'US',
    },
    tags: ['enterprise', 'tech'],
  },
  {
    id: '2',
    firstName: 'Sarah',
    lastName: 'Johnson',
    email: 'sarah.johnson@gmail.com',
    phone: '+1 (555) 987-6543',
    company: 'Johnson Consulting',
    status: 'active',
    customerType: 'business',
    totalOrders: 8,
    totalSpent: 5670.00,
    lastOrderDate: '2024-01-10T14:20:00Z',
    createdAt: '2023-09-20T11:15:00Z',
    updatedAt: '2024-01-10T14:20:00Z',
    address: {
      street: '456 Oak Street',
      city: 'Los Angeles',
      state: 'CA',
      zipCode: '90210',
      country: 'US',
    },
    tags: ['consulting', 'premium'],
  },
  {
    id: '3',
    firstName: 'Michael',
    lastName: 'Chen',
    email: 'mike.chen@personal.com',
    status: 'inactive',
    customerType: 'individual',
    totalOrders: 3,
    totalSpent: 890.00,
    lastOrderDate: '2023-11-15T16:45:00Z',
    createdAt: '2023-03-10T08:30:00Z',
    updatedAt: '2023-11-15T16:45:00Z',
    address: {
      street: '789 Pine Road',
      city: 'Seattle',
      state: 'WA',
      zipCode: '98101',
      country: 'US',
    },
    tags: ['individual'],
  },
  {
    id: '4',
    firstName: 'Emily',
    lastName: 'Rodriguez',
    email: 'emily.rodriguez@startup.io',
    phone: '+1 (555) 456-7890',
    company: 'InnovateTech',
    status: 'pending',
    customerType: 'business',
    totalOrders: 0,
    totalSpent: 0,
    createdAt: '2024-01-18T13:20:00Z',
    updatedAt: '2024-01-18T13:20:00Z',
    tags: ['startup', 'new'],
  },
]

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Simulate data loading
    const loadCustomers = async () => {
      try {
        setIsLoading(true)
        await new Promise(resolve => setTimeout(resolve, 1000)) // Simulate API delay
        setCustomers(mockCustomers)
      } catch (err) {
        setError('Failed to load customers')
      } finally {
        setIsLoading(false)
      }
    }

    loadCustomers()
  }, [])

  const handleRefresh = () => {
    setError(null)
    setCustomers([])
    setIsLoading(true)
    
    // Simulate refresh
    setTimeout(() => {
      setCustomers(mockCustomers)
      setIsLoading(false)
    }, 1000)
  }

  const handleCreate = () => {
    console.log('Create new customer')
    // TODO: Implement create customer modal/form
  }

  const handleEdit = (customer: Customer) => {
    console.log('Edit customer:', customer)
    // TODO: Implement edit customer modal/form
  }

  const handleDelete = (customer: Customer) => {
    console.log('Delete customer:', customer)
    // TODO: Implement delete confirmation dialog
  }

  const handleView = (customer: Customer) => {
    console.log('View customer:', customer)
    // TODO: Navigate to customer details page or open modal
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Customers</h1>
          <p className="text-muted-foreground">
            Manage your customer database and relationships
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add Customer
        </Button>
      </div>

      <CustomersTable
        data={customers}
        isLoading={isLoading}
        error={error}
        onRefresh={handleRefresh}
        onCreate={handleCreate}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onView={handleView}
      />
    </div>
  )
}