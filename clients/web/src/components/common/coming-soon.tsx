import { Construction, CheckCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface ComingSoonPageProps {
  title: string
  description: string
  features?: string[]
  estimatedDate?: string
}

export function ComingSoonPage({ 
  title, 
  description, 
  features = [],
  estimatedDate 
}: ComingSoonPageProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
          <p className="text-muted-foreground">{description}</p>
        </div>
        <Badge variant="secondary">
          <Construction className="mr-1 h-3 w-3" />
          Coming Soon
        </Badge>
      </div>

      <Card>
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4">
            <Construction className="w-8 h-8 text-muted-foreground" />
          </div>
          <CardTitle className="text-xl">This feature is under development</CardTitle>
          <CardDescription className="max-w-md mx-auto">
            We're working hard to bring you this feature. It will include everything you need
            for comprehensive {title.toLowerCase()}.
          </CardDescription>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {features.length > 0 && (
            <div>
              <h3 className="font-semibold mb-3 text-center">Planned Features</h3>
              <div className="grid gap-2 max-w-md mx-auto">
                {features.map((feature, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                    <span className="text-sm">{feature}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {estimatedDate && (
            <div className="text-center">
              <p className="text-sm text-muted-foreground">
                Estimated release: <span className="font-medium">{estimatedDate}</span>
              </p>
            </div>
          )}

          <div className="text-center border-t pt-6">
            <p className="text-sm text-muted-foreground">
              Have suggestions or questions about this feature?{' '}
              <a href="/support" className="text-primary hover:underline">
                Contact our team
              </a>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}