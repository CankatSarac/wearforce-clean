import { Link } from 'react-router-dom'
import { ShoppingCart, Package, Truck, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function ERPPage() {
  const erpModules = [
    {
      title: 'Orders',
      description: 'Manage customer orders and fulfillment',
      href: '/erp/orders',
      icon: ShoppingCart,
      stats: '156 active orders',
    },
    {
      title: 'Inventory',
      description: 'Track stock levels and manage products',
      href: '/erp/inventory',
      icon: Package,
      stats: '1,247 SKUs tracked',
    },
    {
      title: 'Suppliers',
      description: 'Manage vendor relationships and procurement',
      href: '/erp/suppliers',
      icon: Truck,
      stats: '23 active suppliers',
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Enterprise Resource Planning</h1>
        <p className="text-muted-foreground">
          Streamline your business operations and supply chain management
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {erpModules.map((module) => {
          const Icon = module.icon
          return (
            <Card key={module.title} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex items-center space-x-2">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Icon className="h-6 w-6 text-primary" />
                  </div>
                  <CardTitle>{module.title}</CardTitle>
                </div>
                <CardDescription>{module.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-muted-foreground">
                    {module.stats}
                  </span>
                  <Button asChild variant="ghost" size="sm">
                    <Link to={module.href}>
                      View <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}