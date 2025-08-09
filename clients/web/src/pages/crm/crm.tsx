import { Link } from 'react-router-dom'
import { Users, UserPlus, TrendingUp, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function CRMPage() {
  const crmModules = [
    {
      title: 'Customers',
      description: 'Manage customer database and relationships',
      href: '/crm/customers',
      icon: Users,
      stats: '1,247 customers',
    },
    {
      title: 'Leads',
      description: 'Track and nurture potential customers',
      href: '/crm/leads',
      icon: UserPlus,
      stats: '45 active leads',
    },
    {
      title: 'Opportunities',
      description: 'Manage sales opportunities and pipeline',
      href: '/crm/opportunities',
      icon: TrendingUp,
      stats: '$125k in pipeline',
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Customer Relationship Management</h1>
        <p className="text-muted-foreground">
          Manage your customer relationships and sales pipeline
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {crmModules.map((module) => {
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