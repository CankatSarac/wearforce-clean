import { useEffect, useReducer, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { 
  authReducer, 
  initialAuthState, 
  AuthState, 
  AuthAction,
  KeycloakAuth,
  TokenStorage,
  jwtUtils,
  SessionManager,
  SESSION_EVENTS,
} from '@/shared/utils/auth'
import { User, LoginRequest, DeviceInfo } from '@/shared/types/api'

// Web-specific token storage implementation
class WebTokenStorage implements TokenStorage {
  async getAccessToken(): Promise<string | null> {
    return localStorage.getItem('accessToken')
  }

  async setAccessToken(token: string): Promise<void> {
    localStorage.setItem('accessToken', token)
  }

  async getRefreshToken(): Promise<string | null> {
    return localStorage.getItem('refreshToken')
  }

  async setRefreshToken(token: string): Promise<void> {
    localStorage.setItem('refreshToken', token)
  }

  async removeTokens(): Promise<void> {
    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('user')
  }
}

const tokenStorage = new WebTokenStorage()

// Keycloak configuration from environment
const keycloakConfig = {
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'wearforce',
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080/auth',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'wearforce-web',
}

const keycloakAuth = new KeycloakAuth(keycloakConfig, tokenStorage)
const sessionManager = new SessionManager()

export const useAuth = () => {
  const [state, dispatch] = useReducer(authReducer, initialAuthState)
  const navigate = useNavigate()

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        const accessToken = await tokenStorage.getAccessToken()
        const refreshToken = await tokenStorage.getRefreshToken()

        if (accessToken && refreshToken) {
          if (jwtUtils.isExpired(accessToken)) {
            // Try to refresh token
            try {
              const { accessToken: newToken, user } = await keycloakAuth.refreshToken()
              dispatch({
                type: 'TOKEN_REFRESHED',
                payload: { accessToken: newToken, user }
              })
            } catch (error) {
              console.error('Token refresh failed:', error)
              await logout()
            }
          } else {
            // Token is valid, extract user info
            const user = jwtUtils.getUserFromToken(accessToken) as User
            if (user) {
              dispatch({
                type: 'AUTH_SUCCESS',
                payload: {
                  accessToken,
                  refreshToken,
                  user,
                  expiresIn: 0,
                  tokenType: 'Bearer'
                }
              })
            } else {
              await logout()
            }
          }
        }
      } catch (error) {
        console.error('Auth initialization failed:', error)
      } finally {
        dispatch({ type: 'AUTH_LOADING', payload: false })
      }
    }

    initAuth()
  }, [])

  // Setup session management
  useEffect(() => {
    const handleTokenExpired = () => {
      toast.warning('Your session will expire soon', {
        action: {
          label: 'Extend Session',
          onClick: () => refreshToken(),
        },
        duration: 10000,
      })
    }

    const handleSessionExpired = () => {
      toast.error('Your session has expired. Please log in again.')
      logout()
    }

    sessionManager.on(SESSION_EVENTS.TOKEN_EXPIRED, handleTokenExpired)
    sessionManager.on(SESSION_EVENTS.SESSION_EXPIRED, handleSessionExpired)

    return () => {
      sessionManager.off(SESSION_EVENTS.TOKEN_EXPIRED, handleTokenExpired)
      sessionManager.off(SESSION_EVENTS.SESSION_EXPIRED, handleSessionExpired)
      sessionManager.cleanup()
    }
  }, [])

  const login = useCallback(async (credentials: LoginRequest) => {
    try {
      dispatch({ type: 'AUTH_LOADING', payload: true })

      const response = await keycloakAuth.login(credentials.email, credentials.password)
      
      // Store user data
      localStorage.setItem('user', JSON.stringify(response.user))

      dispatch({
        type: 'AUTH_SUCCESS',
        payload: response
      })

      sessionManager.updateActivity()
      
      toast.success(`Welcome back, ${response.user.firstName}!`)
      
      // Redirect to dashboard or intended page
      const redirectPath = sessionStorage.getItem('redirectAfterLogin') || '/dashboard'
      sessionStorage.removeItem('redirectAfterLogin')
      navigate(redirectPath)
      
      return response
    } catch (error: any) {
      const message = error.message || 'Login failed'
      dispatch({
        type: 'AUTH_ERROR',
        payload: message
      })
      toast.error(message)
      throw error
    }
  }, [navigate])

  const logout = useCallback(async () => {
    try {
      await keycloakAuth.logout()
      
      dispatch({ type: 'AUTH_LOGOUT' })
      sessionManager.cleanup()
      
      // Clear any cached data
      localStorage.removeItem('user')
      
      toast.success('Logged out successfully')
      navigate('/auth/login')
    } catch (error) {
      console.error('Logout error:', error)
      // Even if logout fails, clear local state
      dispatch({ type: 'AUTH_LOGOUT' })
      navigate('/auth/login')
    }
  }, [navigate])

  const refreshToken = useCallback(async () => {
    try {
      const { accessToken, user } = await keycloakAuth.refreshToken()
      
      dispatch({
        type: 'TOKEN_REFRESHED',
        payload: { accessToken, user }
      })

      sessionManager.updateActivity()
      
      if (user) {
        localStorage.setItem('user', JSON.stringify(user))
      }
      
      return accessToken
    } catch (error: any) {
      console.error('Token refresh failed:', error)
      await logout()
      throw error
    }
  }, [logout])

  const updateUser = useCallback((userData: Partial<User>) => {
    if (state.user) {
      const updatedUser = { ...state.user, ...userData }
      localStorage.setItem('user', JSON.stringify(updatedUser))
      
      dispatch({
        type: 'TOKEN_REFRESHED',
        payload: { 
          accessToken: state.accessToken!, 
          user: updatedUser 
        }
      })
    }
  }, [state.user, state.accessToken])

  const clearError = useCallback(() => {
    dispatch({ type: 'CLEAR_ERROR' })
  }, [])

  const hasPermission = useCallback((resource: string, action: string): boolean => {
    if (!state.user || !state.user.permissions) return false
    
    return state.user.permissions.some(permission => 
      permission.resource === resource && 
      permission.actions.includes(action)
    )
  }, [state.user])

  const hasRole = useCallback((roleName: string): boolean => {
    if (!state.user || !state.user.role) return false
    return state.user.role.name === roleName
  }, [state.user])

  const hasAnyRole = useCallback((roleNames: string[]): boolean => {
    if (!state.user || !state.user.role) return false
    return roleNames.includes(state.user.role.name)
  }, [state.user])

  const isRoleLevel = useCallback((minLevel: number): boolean => {
    if (!state.user || !state.user.role) return false
    return state.user.role.level >= minLevel
  }, [state.user])

  const getSessionRemainingTime = useCallback((): number => {
    return sessionManager.getRemainingTime()
  }, [])

  const extendSession = useCallback((): void => {
    sessionManager.updateActivity()
  }, [])

  return {
    // State
    user: state.user,
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    error: state.error,
    accessToken: state.accessToken,

    // Actions
    login,
    logout,
    refreshToken,
    updateUser,
    clearError,

    // Authorization helpers
    hasPermission,
    hasRole,
    hasAnyRole,
    isRoleLevel,

    // Session management
    getSessionRemainingTime,
    extendSession,
  }
}