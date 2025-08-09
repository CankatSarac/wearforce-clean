import { ReactNode, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

interface ProtectedRouteProps {
  children: ReactNode
  requireAuth?: boolean
  redirectTo?: string
  requiredRole?: string
  requiredPermissions?: Array<{ resource: string; action: string }>
}

export function ProtectedRoute({
  children,
  requireAuth = true,
  redirectTo = '/auth/login',
  requiredRole,
  requiredPermissions = [],
}: ProtectedRouteProps) {
  const { 
    isAuthenticated, 
    isLoading, 
    user, 
    hasRole, 
    hasPermission 
  } = useAuth()
  const location = useLocation()

  useEffect(() => {
    // Store the current location to redirect back after login
    if (!isAuthenticated && requireAuth) {
      sessionStorage.setItem('redirectAfterLogin', location.pathname + location.search)
    }
  }, [isAuthenticated, requireAuth, location])

  // Show loading spinner while authentication is being checked
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Redirect to login if authentication is required but user is not authenticated
  if (requireAuth && !isAuthenticated) {
    return <Navigate to={redirectTo} replace />
  }

  // Redirect to dashboard if user is already authenticated and tries to access auth pages
  if (!requireAuth && isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  // Check role-based access
  if (isAuthenticated && requiredRole && !hasRole(requiredRole)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold text-destructive">Access Denied</h1>
          <p className="text-muted-foreground">
            You don't have the required role ({requiredRole}) to access this page.
          </p>
          <p className="text-sm text-muted-foreground">
            Your current role: {user?.role?.name || 'No role assigned'}
          </p>
        </div>
      </div>
    )
  }

  // Check permission-based access
  if (isAuthenticated && requiredPermissions.length > 0) {
    const hasRequiredPermissions = requiredPermissions.every(permission =>
      hasPermission(permission.resource, permission.action)
    )

    if (!hasRequiredPermissions) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center space-y-4">
            <h1 className="text-2xl font-bold text-destructive">Access Denied</h1>
            <p className="text-muted-foreground">
              You don't have the required permissions to access this page.
            </p>
            <div className="text-sm text-muted-foreground">
              <p>Required permissions:</p>
              <ul className="list-disc list-inside mt-2">
                {requiredPermissions.map((permission, index) => (
                  <li key={index}>
                    {permission.action} on {permission.resource}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )
    }
  }

  return <>{children}</>
}