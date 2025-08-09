import { useState, useEffect } from 'react'
import { OrdersTable, type Order } from '@/components/tables/orders-table'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

// Mock data for development
const mockOrders: Order[] = [
  {
    id: '1',
    orderNumber: 'ORD-2024-0001',
    customerId: '1',
    customerName: 'John Doe',
    customerEmail: 'john.doe@example.com',
    status: 'processing',
    paymentStatus: 'paid',
    total: 1299.99,
    subtotal: 1199.99,
    tax: 100.00,
    shipping: 0.00,
    currency: 'USD',
    items: [
      {
        id: '1',
        name: 'Premium Wireless Headphones',
        quantity: 2,
        price: 159.99,
        sku: 'PWH-001',
      },
      {
        id: '2',
        name: 'Smart Fitness Tracker',
        quantity: 1,
        price: 249.99,
        sku: 'SFT-002',
      },
    ],
    shippingAddress: {
      street: '123 Business Ave',
      city: 'San Francisco',
      state: 'CA',
      zipCode: '94105',
      country: 'US',
    },
    trackingNumber: 'TRK123456789',
    createdAt: '2024-01-18T10:30:00Z',
    updatedAt: '2024-01-18T14:20:00Z',
  },
  {
    id: '2',
    orderNumber: 'ORD-2024-0002',
    customerId: '2',
    customerName: 'Sarah Johnson',
    customerEmail: 'sarah.johnson@gmail.com',
    status: 'shipped',
    paymentStatus: 'paid',
    total: 499.99,
    subtotal: 449.99,
    tax: 50.00,
    shipping: 0.00,
    currency: 'USD',
    items: [
      {
        id: '3',
        name: 'Wireless Charging Pad',
        quantity: 5,
        price: 89.99,
        sku: 'WCP-003',
      },
    ],
    shippingAddress: {
      street: '456 Oak Street',
      city: 'Los Angeles',
      state: 'CA',
      zipCode: '90210',
      country: 'US',
    },
    trackingNumber: 'TRK987654321',
    createdAt: '2024-01-17T15:45:00Z',
    updatedAt: '2024-01-18T09:15:00Z',
    shippedAt: '2024-01-18T09:15:00Z',
  },
  {
    id: '3',
    orderNumber: 'ORD-2024-0003',
    customerId: '3',
    customerName: 'Michael Chen',
    customerEmail: 'mike.chen@personal.com',
    status: 'delivered',
    paymentStatus: 'paid',
    total: 89.99,
    subtotal: 79.99,
    tax: 10.00,
    shipping: 0.00,
    currency: 'USD',
    items: [
      {
        id: '4',
        name: 'USB-C Cable',
        quantity: 3,
        price: 19.99,
        sku: 'USC-004',
      },
    ],
    shippingAddress: {
      street: '789 Pine Road',
      city: 'Seattle',
      state: 'WA',
      zipCode: '98101',
      country: 'US',
    },
    trackingNumber: 'TRK456789123',
    createdAt: '2024-01-15T11:20:00Z',
    updatedAt: '2024-01-16T16:30:00Z',
    shippedAt: '2024-01-15T18:00:00Z',
    deliveredAt: '2024-01-16T16:30:00Z',
  },
  {
    id: '4',
    orderNumber: 'ORD-2024-0004',
    customerId: '4',
    customerName: 'Emily Rodriguez',
    customerEmail: 'emily.rodriguez@startup.io',
    status: 'pending',
    paymentStatus: 'pending',
    total: 2199.99,
    subtotal: 1999.99,
    tax: 200.00,
    shipping: 0.00,
    currency: 'USD',
    items: [
      {
        id: '5',
        name: 'Professional Monitor',
        quantity: 2,
        price: 999.99,
        sku: 'PM-005',
      },
    ],
    shippingAddress: {
      street: '321 Innovation Dr',
      city: 'Austin',
      state: 'TX',
      zipCode: '73301',
      country: 'US',
    },
    createdAt: '2024-01-18T16:45:00Z',
    updatedAt: '2024-01-18T16:45:00Z',
  },
]

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Simulate data loading
    const loadOrders = async () => {
      try {
        setIsLoading(true)
        await new Promise(resolve => setTimeout(resolve, 1000)) // Simulate API delay
        setOrders(mockOrders)
      } catch (err) {
        setError('Failed to load orders')
      } finally {
        setIsLoading(false)
      }
    }

    loadOrders()
  }, [])

  const handleRefresh = () => {
    setError(null)
    setOrders([])
    setIsLoading(true)
    
    // Simulate refresh
    setTimeout(() => {
      setOrders(mockOrders)
      setIsLoading(false)
    }, 1000)
  }

  const handleCreate = () => {
    console.log('Create new order')
    // TODO: Implement create order modal/form
  }

  const handleEdit = (order: Order) => {
    console.log('Edit order:', order)
    // TODO: Implement edit order modal/form
  }

  const handleCancel = (order: Order) => {
    console.log('Cancel order:', order)
    // TODO: Implement cancel confirmation dialog
    
    // Update order status locally for demo
    setOrders(prev => prev.map(o => 
      o.id === order.id 
        ? { ...o, status: 'cancelled', updatedAt: new Date().toISOString() }
        : o
    ))
  }

  const handleView = (order: Order) => {
    console.log('View order:', order)
    // TODO: Navigate to order details page or open modal
  }

  const handleUpdateStatus = (order: Order, newStatus: Order['status']) => {
    console.log('Update order status:', order, newStatus)
    
    // Update order status locally for demo
    const now = new Date().toISOString()
    setOrders(prev => prev.map(o => {
      if (o.id === order.id) {
        const updates: Partial<Order> = {
          status: newStatus,
          updatedAt: now,
        }
        
        if (newStatus === 'shipped' && !o.shippedAt) {
          updates.shippedAt = now
          updates.trackingNumber = `TRK${Math.random().toString().substr(2, 9)}`
        } else if (newStatus === 'delivered' && !o.deliveredAt) {
          updates.deliveredAt = now
        }
        
        return { ...o, ...updates }
      }
      return o
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Orders</h1>
          <p className="text-muted-foreground">
            Manage customer orders and fulfillment
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          New Order
        </Button>
      </div>

      <OrdersTable
        data={orders}
        isLoading={isLoading}
        error={error}
        onRefresh={handleRefresh}
        onCreate={handleCreate}
        onEdit={handleEdit}
        onCancel={handleCancel}
        onView={handleView}
        onUpdateStatus={handleUpdateStatus}
      />
    </div>
  )
}