import { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'

interface AuthLayoutProps {
  children: ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-muted/30 to-background p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Logo and Brand */}
        <div className="text-center space-y-2">
          <div className="mx-auto w-16 h-16 bg-primary rounded-2xl flex items-center justify-center">
            <span className="text-2xl font-bold text-primary-foreground">W</span>
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">WearForce</h1>
            <p className="text-sm text-muted-foreground">
              Conversational AI for Business Operations
            </p>
          </div>
        </div>

        {/* Auth Form */}
        <Card>
          <CardContent className="p-6">
            {children}
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-xs text-muted-foreground">
          <p>© 2024 WearForce. All rights reserved.</p>
          <div className="flex justify-center space-x-4 mt-2">
            <a href="/privacy" className="hover:text-foreground transition-colors">
              Privacy Policy
            </a>
            <a href="/terms" className="hover:text-foreground transition-colors">
              Terms of Service
            </a>
            <a href="/support" className="hover:text-foreground transition-colors">
              Support
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}