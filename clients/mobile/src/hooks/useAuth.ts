import { useEffect, useReducer, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import EncryptedStorage from 'react-native-encrypted-storage';
import { Alert } from 'react-native';

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
  getDeviceInfo,
} from '../shared/utils/auth';
import { User, LoginRequest } from '../shared/types/api';

// React Native specific token storage implementation
class ReactNativeTokenStorage implements TokenStorage {
  async getAccessToken(): Promise<string | null> {
    try {
      return await EncryptedStorage.getItem('accessToken');
    } catch {
      // Fallback to AsyncStorage for older versions
      return await AsyncStorage.getItem('accessToken');
    }
  }

  async setAccessToken(token: string): Promise<void> {
    try {
      await EncryptedStorage.setItem('accessToken', token);
    } catch {
      await AsyncStorage.setItem('accessToken', token);
    }
  }

  async getRefreshToken(): Promise<string | null> {
    try {
      return await EncryptedStorage.getItem('refreshToken');
    } catch {
      return await AsyncStorage.getItem('refreshToken');
    }
  }

  async setRefreshToken(token: string): Promise<void> {
    try {
      await EncryptedStorage.setItem('refreshToken', token);
    } catch {
      await AsyncStorage.setItem('refreshToken', token);
    }
  }

  async removeTokens(): Promise<void> {
    try {
      await EncryptedStorage.clear();
    } catch {
      await AsyncStorage.multiRemove(['accessToken', 'refreshToken', 'user']);
    }
  }
}

const tokenStorage = new ReactNativeTokenStorage();

// Get device info for React Native
const getReactNativeDeviceInfo = () => {
  return {
    platform: 'mobile' as const,
    deviceId: 'device-id-from-device-info', // Would use react-native-device-info
    appVersion: '1.0.0', // From app config
    osVersion: 'OS version', // From react-native-device-info
    deviceName: 'Device name', // From react-native-device-info
  };
};

// Keycloak configuration
const keycloakConfig = {
  realm: 'wearforce',
  url: 'https://auth.wearforce.com',
  clientId: 'wearforce-mobile',
};

const keycloakAuth = new KeycloakAuth(keycloakConfig, tokenStorage);

export const useAuth = () => {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        dispatch({ type: 'AUTH_LOADING', payload: true });

        const accessToken = await tokenStorage.getAccessToken();
        const refreshToken = await tokenStorage.getRefreshToken();

        if (accessToken && refreshToken) {
          if (jwtUtils.isExpired(accessToken)) {
            // Try to refresh token
            try {
              const { accessToken: newToken, user } = await keycloakAuth.refreshToken();
              dispatch({
                type: 'TOKEN_REFRESHED',
                payload: { accessToken: newToken, user }
              });
            } catch (error) {
              console.error('Token refresh failed:', error);
              await logout();
            }
          } else {
            // Token is valid, extract user info
            const user = jwtUtils.getUserFromToken(accessToken) as User;
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
              });
            } else {
              await logout();
            }
          }
        }
      } catch (error) {
        console.error('Auth initialization failed:', error);
      } finally {
        dispatch({ type: 'AUTH_LOADING', payload: false });
      }
    };

    initAuth();
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    try {
      dispatch({ type: 'AUTH_LOADING', payload: true });

      // Add device info to login request
      const loginData = {
        ...credentials,
        deviceInfo: getReactNativeDeviceInfo(),
      };

      const response = await keycloakAuth.login(loginData.email, loginData.password);
      
      // Store user data
      await AsyncStorage.setItem('user', JSON.stringify(response.user));

      dispatch({
        type: 'AUTH_SUCCESS',
        payload: response
      });
      
      return response;
    } catch (error: any) {
      const message = error.message || 'Login failed';
      dispatch({
        type: 'AUTH_ERROR',
        payload: message
      });
      
      // Show native alert
      Alert.alert('Login Failed', message);
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await keycloakAuth.logout();
      
      dispatch({ type: 'AUTH_LOGOUT' });
      
      // Clear any cached data
      await AsyncStorage.removeItem('user');
      
    } catch (error) {
      console.error('Logout error:', error);
      // Even if logout fails, clear local state
      dispatch({ type: 'AUTH_LOGOUT' });
    }
  }, []);

  const refreshToken = useCallback(async () => {
    try {
      const { accessToken, user } = await keycloakAuth.refreshToken();
      
      dispatch({
        type: 'TOKEN_REFRESHED',
        payload: { accessToken, user }
      });
      
      if (user) {
        await AsyncStorage.setItem('user', JSON.stringify(user));
      }
      
      return accessToken;
    } catch (error: any) {
      console.error('Token refresh failed:', error);
      await logout();
      throw error;
    }
  }, [logout]);

  const updateUser = useCallback(async (userData: Partial<User>) => {
    if (state.user) {
      const updatedUser = { ...state.user, ...userData };
      await AsyncStorage.setItem('user', JSON.stringify(updatedUser));
      
      dispatch({
        type: 'TOKEN_REFRESHED',
        payload: { 
          accessToken: state.accessToken!, 
          user: updatedUser 
        }
      });
    }
  }, [state.user, state.accessToken]);

  const clearError = useCallback(() => {
    dispatch({ type: 'CLEAR_ERROR' });
  }, []);

  const hasPermission = useCallback((resource: string, action: string): boolean => {
    if (!state.user || !state.user.permissions) return false;
    
    return state.user.permissions.some(permission => 
      permission.resource === resource && 
      permission.actions.includes(action)
    );
  }, [state.user]);

  const hasRole = useCallback((roleName: string): boolean => {
    if (!state.user || !state.user.role) return false;
    return state.user.role.name === roleName;
  }, [state.user]);

  const hasAnyRole = useCallback((roleNames: string[]): boolean => {
    if (!state.user || !state.user.role) return false;
    return roleNames.includes(state.user.role.name);
  }, [state.user]);

  const isRoleLevel = useCallback((minLevel: number): boolean => {
    if (!state.user || !state.user.role) return false;
    return state.user.role.level >= minLevel;
  }, [state.user]);

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
  };
};