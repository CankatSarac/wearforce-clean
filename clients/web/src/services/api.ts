import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

// Secure token management utilities
class TokenManager {
  private static readonly ACCESS_TOKEN_COOKIE = 'wf_access_token'
  private static readonly REFRESH_TOKEN_COOKIE = 'wf_refresh_token'
  private static readonly CSRF_TOKEN_HEADER = 'X-CSRF-Token'

  static getAccessToken(): string | null {
    // Try to get from httpOnly cookie first (handled by browser automatically)
    // Fall back to sessionStorage for SPA mode
    return sessionStorage.getItem('access_token')
  }

  static getRefreshToken(): string | null {
    // Refresh token should only be in httpOnly cookie for security
    // This method is mainly for logout cleanup
    return null // Browser will handle httpOnly cookie automatically
  }

  static setTokens(accessToken: string, refreshToken?: string): void {
    // Store access token in sessionStorage (more secure than localStorage)
    if (accessToken) {
      sessionStorage.setItem('access_token', accessToken)
    }
    // Refresh token will be set as httpOnly cookie by server
  }

  static clearTokens(): void {
    // Clear sessionStorage
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user')
    
    // Clear cookies by making logout request to server
    // Server will clear httpOnly cookies
  }

  static getCsrfToken(): string | null {
    // Get CSRF token from meta tag or cookie
    const metaToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
    if (metaToken) return metaToken
    
    return this.getCookie('csrf_token')
  }

  private static getCookie(name: string): string | null {
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || null
    }
    return null
  }

  static isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.exp * 1000 < Date.now()
    } catch {
      return true
    }
  }
}

export interface ApiResponse<T = any> {
  success: boolean
  data: T
  message?: string
  error?: string
}

export interface PaginationParams {
  page?: number
  limit?: number
  sort?: string
  order?: 'asc' | 'desc'
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  totalPages: number
}

class ApiService {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000/api',
      timeout: 30000,
      withCredentials: true, // Include cookies in requests
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor to add auth token and CSRF token
    this.client.interceptors.request.use(
      (config) => {
        const token = TokenManager.getAccessToken()
        if (token && !TokenManager.isTokenExpired(token)) {
          config.headers.Authorization = `Bearer ${token}`
        }

        // Add CSRF token for state-changing requests
        const csrfToken = TokenManager.getCsrfToken()
        if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase() || '')) {
          config.headers['X-CSRF-Token'] = csrfToken
        }

        // Add security headers
        config.headers['X-Requested-With'] = 'XMLHttpRequest'
        
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor to handle errors and token refresh
    this.client.interceptors.response.use(
      (response) => {
        // Extract new access token from response headers if present
        const newToken = response.headers['x-new-access-token']
        if (newToken) {
          TokenManager.setTokens(newToken)
        }
        return response
      },
      async (error) => {
        const originalRequest = error.config

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true

          try {
            // Try to refresh token via cookie-based endpoint
            const response = await this.client.post('/auth/refresh', {}, {
              withCredentials: true // Send httpOnly refresh cookie
            })
            
            const { accessToken } = response.data
            if (accessToken) {
              TokenManager.setTokens(accessToken)
              
              // Retry original request with new token
              originalRequest.headers.Authorization = `Bearer ${accessToken}`
              return this.client(originalRequest)
            }
          } catch (refreshError) {
            // Refresh failed, clear tokens and redirect to login
            TokenManager.clearTokens()
            
            // Make logout request to clear server-side cookies
            try {
              await this.client.post('/auth/logout', {}, { withCredentials: true })
            } catch {
              // Ignore logout errors
            }
            
            window.location.href = '/auth/login'
            return Promise.reject(refreshError)
          }
        }

        // Handle CSRF token errors
        if (error.response?.status === 403 && error.response?.data?.error === 'CSRF_TOKEN_MISMATCH') {
          // Reload page to get new CSRF token
          window.location.reload()
          return Promise.reject(error)
        }

        return Promise.reject(error)
      }
    )
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response: AxiosResponse<ApiResponse<T>> = await this.client.get(url, config)
    return response.data
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response: AxiosResponse<ApiResponse<T>> = await this.client.post(url, data, config)
    return response.data
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response: AxiosResponse<ApiResponse<T>> = await this.client.put(url, data, config)
    return response.data
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response: AxiosResponse<ApiResponse<T>> = await this.client.patch(url, data, config)
    return response.data
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response: AxiosResponse<ApiResponse<T>> = await this.client.delete(url, config)
    return response.data
  }

  // Convenience methods for common operations
  async getPaginated<T = any>(
    url: string, 
    params?: PaginationParams & Record<string, any>
  ): Promise<ApiResponse<PaginatedResponse<T>>> {
    return this.get(url, { params })
  }

  async uploadFile<T = any>(
    url: string, 
    file: File, 
    onUploadProgress?: (progressEvent: any) => void
  ): Promise<ApiResponse<T>> {
    const formData = new FormData()
    formData.append('file', file)

    return this.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
    })
  }

  async downloadFile(url: string, filename?: string): Promise<void> {
    const response = await this.client.get(url, {
      responseType: 'blob',
    })

    const blob = new Blob([response.data])
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
  }

  // Authentication methods
  async login(credentials: { email: string; password: string }): Promise<ApiResponse<{ user: any; accessToken: string }>> {
    const response = await this.post('/auth/login', credentials)
    
    if (response.success && response.data.accessToken) {
      TokenManager.setTokens(response.data.accessToken)
    }
    
    return response
  }

  async logout(): Promise<void> {
    try {
      await this.post('/auth/logout', {}, { withCredentials: true })
    } catch {
      // Continue with logout even if server request fails
    } finally {
      TokenManager.clearTokens()
      window.location.href = '/auth/login'
    }
  }

  async refreshToken(): Promise<boolean> {
    try {
      const response = await this.post('/auth/refresh', {}, { withCredentials: true })
      
      if (response.success && response.data.accessToken) {
        TokenManager.setTokens(response.data.accessToken)
        return true
      }
    } catch {
      TokenManager.clearTokens()
    }
    return false
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      await this.get('/health')
      return true
    } catch {
      return false
    }
  }

  // Security utilities
  getCurrentToken(): string | null {
    return TokenManager.getAccessToken()
  }

  isAuthenticated(): boolean {
    const token = TokenManager.getAccessToken()
    return token !== null && !TokenManager.isTokenExpired(token)
  }
}

export const apiService = new ApiService()
export { TokenManager }
export default apiService