// Shared authentication utilities and patterns

import { User, LoginResponse, DeviceInfo } from '../types/api';

// Token management interface that can be implemented per platform
export interface TokenStorage {
  getAccessToken(): Promise<string | null>;
  setAccessToken(token: string): Promise<void>;
  getRefreshToken(): Promise<string | null>;
  setRefreshToken(token: string): Promise<void>;
  removeTokens(): Promise<void>;
}

// JWT token utilities
export const jwtUtils = {
  decode: (token: string): any => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      return null;
    }
  },

  isExpired: (token: string): boolean => {
    try {
      const payload = jwtUtils.decode(token);
      if (!payload || !payload.exp) return true;
      
      const currentTime = Math.floor(Date.now() / 1000);
      return payload.exp < currentTime;
    } catch {
      return true;
    }
  },

  getExpirationTime: (token: string): number | null => {
    try {
      const payload = jwtUtils.decode(token);
      return payload?.exp ? payload.exp * 1000 : null;
    } catch {
      return null;
    }
  },

  getUserFromToken: (token: string): Partial<User> | null => {
    try {
      const payload = jwtUtils.decode(token);
      if (!payload) return null;

      return {
        id: payload.sub,
        email: payload.email,
        firstName: payload.firstName || payload.given_name,
        lastName: payload.lastName || payload.family_name,
        role: payload.role,
        permissions: payload.permissions || [],
      };
    } catch {
      return null;
    }
  },
};

// Authentication state management
export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export const initialAuthState: AuthState = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
};

// Authentication actions
export type AuthAction =
  | { type: 'AUTH_LOADING'; payload: boolean }
  | { type: 'AUTH_SUCCESS'; payload: LoginResponse }
  | { type: 'AUTH_ERROR'; payload: string }
  | { type: 'AUTH_LOGOUT' }
  | { type: 'TOKEN_REFRESHED'; payload: { accessToken: string; user?: User } }
  | { type: 'CLEAR_ERROR' };

export const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'AUTH_LOADING':
      return {
        ...state,
        isLoading: action.payload,
        error: null,
      };

    case 'AUTH_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        accessToken: action.payload.accessToken,
        refreshToken: action.payload.refreshToken,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      };

    case 'AUTH_ERROR':
      return {
        ...state,
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
        isLoading: false,
        error: action.payload,
      };

    case 'AUTH_LOGOUT':
      return {
        ...initialAuthState,
        isLoading: false,
      };

    case 'TOKEN_REFRESHED':
      return {
        ...state,
        accessToken: action.payload.accessToken,
        user: action.payload.user || state.user,
        isAuthenticated: true,
        error: null,
      };

    case 'CLEAR_ERROR':
      return {
        ...state,
        error: null,
      };

    default:
      return state;
  }
};

// Platform-specific device info generators
export const getDeviceInfo = (): DeviceInfo => {
  // This would be implemented differently for each platform
  if (typeof window !== 'undefined') {
    // Web platform
    return {
      platform: 'web',
      deviceId: getOrCreateDeviceId(),
      appVersion: process.env.REACT_APP_VERSION || '1.0.0',
      osVersion: navigator.userAgent,
      deviceName: getBrowserInfo(),
    };
  }
  
  // Default fallback
  return {
    platform: 'web',
    deviceId: 'unknown',
    appVersion: '1.0.0',
  };
};

const getOrCreateDeviceId = (): string => {
  let deviceId = localStorage.getItem('deviceId');
  if (!deviceId) {
    deviceId = generateDeviceId();
    localStorage.setItem('deviceId', deviceId);
  }
  return deviceId;
};

const generateDeviceId = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const getBrowserInfo = (): string => {
  const ua = navigator.userAgent;
  if (ua.includes('Chrome')) return 'Chrome';
  if (ua.includes('Firefox')) return 'Firefox';
  if (ua.includes('Safari')) return 'Safari';
  if (ua.includes('Edge')) return 'Edge';
  return 'Unknown';
};

// Keycloak integration utilities
export interface KeycloakConfig {
  realm: string;
  url: string;
  clientId: string;
  clientSecret?: string;
}

export class KeycloakAuth {
  private config: KeycloakConfig;
  private tokenStorage: TokenStorage;

  constructor(config: KeycloakConfig, tokenStorage: TokenStorage) {
    this.config = config;
    this.tokenStorage = tokenStorage;
  }

  async login(email: string, password: string): Promise<LoginResponse> {
    const tokenUrl = `${this.config.url}/realms/${this.config.realm}/protocol/openid-connect/token`;
    
    const params = new URLSearchParams();
    params.append('grant_type', 'password');
    params.append('client_id', this.config.clientId);
    if (this.config.clientSecret) {
      params.append('client_secret', this.config.clientSecret);
    }
    params.append('username', email);
    params.append('password', password);

    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error_description || 'Login failed');
    }

    const tokenResponse = await response.json();
    
    // Store tokens
    await this.tokenStorage.setAccessToken(tokenResponse.access_token);
    await this.tokenStorage.setRefreshToken(tokenResponse.refresh_token);

    // Extract user info from token
    const user = jwtUtils.getUserFromToken(tokenResponse.access_token) as User;

    return {
      accessToken: tokenResponse.access_token,
      refreshToken: tokenResponse.refresh_token,
      expiresIn: tokenResponse.expires_in,
      tokenType: tokenResponse.token_type,
      user,
    };
  }

  async refreshToken(): Promise<{ accessToken: string; user?: User }> {
    const refreshToken = await this.tokenStorage.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const tokenUrl = `${this.config.url}/realms/${this.config.realm}/protocol/openid-connect/token`;
    
    const params = new URLSearchParams();
    params.append('grant_type', 'refresh_token');
    params.append('client_id', this.config.clientId);
    if (this.config.clientSecret) {
      params.append('client_secret', this.config.clientSecret);
    }
    params.append('refresh_token', refreshToken);

    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params,
    });

    if (!response.ok) {
      await this.tokenStorage.removeTokens();
      throw new Error('Token refresh failed');
    }

    const tokenResponse = await response.json();
    
    // Store new tokens
    await this.tokenStorage.setAccessToken(tokenResponse.access_token);
    if (tokenResponse.refresh_token) {
      await this.tokenStorage.setRefreshToken(tokenResponse.refresh_token);
    }

    // Extract user info if needed
    const user = jwtUtils.getUserFromToken(tokenResponse.access_token) as User;

    return {
      accessToken: tokenResponse.access_token,
      user,
    };
  }

  async logout(): Promise<void> {
    const refreshToken = await this.tokenStorage.getRefreshToken();
    
    if (refreshToken) {
      try {
        const logoutUrl = `${this.config.url}/realms/${this.config.realm}/protocol/openid-connect/logout`;
        
        const params = new URLSearchParams();
        params.append('client_id', this.config.clientId);
        if (this.config.clientSecret) {
          params.append('client_secret', this.config.clientSecret);
        }
        params.append('refresh_token', refreshToken);

        await fetch(logoutUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: params,
        });
      } catch (error) {
        console.warn('Keycloak logout failed:', error);
      }
    }

    // Always clear local tokens
    await this.tokenStorage.removeTokens();
  }

  async getUserInfo(): Promise<User> {
    const accessToken = await this.tokenStorage.getAccessToken();
    if (!accessToken) {
      throw new Error('No access token available');
    }

    const userInfoUrl = `${this.config.url}/realms/${this.config.realm}/protocol/openid-connect/userinfo`;
    
    const response = await fetch(userInfoUrl, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user info');
    }

    return response.json();
  }
}

// Authorization utilities
export const hasPermission = (user: User | null, resource: string, action: string): boolean => {
  if (!user || !user.permissions) return false;

  return user.permissions.some(permission => 
    permission.resource === resource && 
    permission.actions.includes(action)
  );
};

export const hasRole = (user: User | null, roleName: string): boolean => {
  if (!user || !user.role) return false;
  return user.role.name === roleName;
};

export const hasAnyRole = (user: User | null, roleNames: string[]): boolean => {
  if (!user || !user.role) return false;
  return roleNames.includes(user.role.name);
};

export const isRoleLevel = (user: User | null, minLevel: number): boolean => {
  if (!user || !user.role) return false;
  return user.role.level >= minLevel;
};

// Request interceptor for adding auth headers
export const createAuthInterceptor = (tokenStorage: TokenStorage) => {
  return async (config: any) => {
    const token = await tokenStorage.getAccessToken();
    if (token && !jwtUtils.isExpired(token)) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${token}`,
      };
    }
    return config;
  };
};

// Response interceptor for handling auth errors
export const createAuthErrorInterceptor = (
  tokenStorage: TokenStorage,
  onTokenRefresh: (newToken: string) => void,
  onLogout: () => void
) => {
  return async (error: any) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = await tokenStorage.getRefreshToken();
        if (refreshToken) {
          // Try to refresh token
          const keycloak = new KeycloakAuth(
            // This would need to be provided from environment/config
            {} as KeycloakConfig,
            tokenStorage
          );
          
          const { accessToken } = await keycloak.refreshToken();
          onTokenRefresh(accessToken);

          // Retry original request
          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
          return Promise.resolve(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, logout user
        onLogout();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  };
};

// Session management utilities
export const SESSION_EVENTS = {
  TOKEN_EXPIRED: 'tokenExpired',
  SESSION_EXPIRED: 'sessionExpired',
  USER_ACTIVITY: 'userActivity',
} as const;

export class SessionManager {
  private lastActivity: number = Date.now();
  private sessionTimeout: number = 30 * 60 * 1000; // 30 minutes
  private warningTimeout: number = 5 * 60 * 1000; // 5 minutes
  private checkInterval: NodeJS.Timeout | null = null;
  private eventListeners: Record<string, Function[]> = {};

  constructor(sessionTimeout = 30 * 60 * 1000, warningTimeout = 5 * 60 * 1000) {
    this.sessionTimeout = sessionTimeout;
    this.warningTimeout = warningTimeout;
    this.setupActivityListeners();
    this.startSessionCheck();
  }

  private setupActivityListeners() {
    if (typeof window === 'undefined') return;

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    
    const updateActivity = () => {
      this.lastActivity = Date.now();
      this.emit(SESSION_EVENTS.USER_ACTIVITY, this.lastActivity);
    };

    events.forEach(event => {
      document.addEventListener(event, updateActivity, true);
    });
  }

  private startSessionCheck() {
    this.checkInterval = setInterval(() => {
      const timeSinceLastActivity = Date.now() - this.lastActivity;
      
      if (timeSinceLastActivity >= this.sessionTimeout) {
        this.emit(SESSION_EVENTS.SESSION_EXPIRED);
        this.cleanup();
      } else if (timeSinceLastActivity >= this.sessionTimeout - this.warningTimeout) {
        this.emit(SESSION_EVENTS.TOKEN_EXPIRED);
      }
    }, 60000); // Check every minute
  }

  updateActivity() {
    this.lastActivity = Date.now();
  }

  getRemainingTime(): number {
    return Math.max(0, this.sessionTimeout - (Date.now() - this.lastActivity));
  }

  on(event: string, callback: Function) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  off(event: string, callback: Function) {
    if (this.eventListeners[event]) {
      this.eventListeners[event] = this.eventListeners[event].filter(cb => cb !== callback);
    }
  }

  private emit(event: string, data?: any) {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach(callback => callback(data));
    }
  }

  cleanup() {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
    this.eventListeners = {};
  }
}

// Password utilities
export const generateSecurePassword = (length = 16): string => {
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
  let password = '';
  
  for (let i = 0; i < length; i++) {
    password += charset.charAt(Math.floor(Math.random() * charset.length));
  }
  
  return password;
};

export const hashPassword = async (password: string, salt?: string): Promise<{ hash: string; salt: string }> => {
  // This is a simplified version - in production, use proper crypto libraries
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const encoder = new TextEncoder();
    const data = encoder.encode(password + (salt || ''));
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    
    return {
      hash,
      salt: salt || Math.random().toString(36),
    };
  }
  
  // Fallback for environments without crypto.subtle
  throw new Error('Crypto API not available');
};