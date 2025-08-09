import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// Types
export interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string;
  expires_in: number;
  interval: number;
}

export interface TokenResponse {
  access_token?: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
  scope?: string;
  error?: string;
  error_description?: string;
}

export interface DeviceFlowConfig {
  clientId: string;
  baseURL: string;
  scope?: string;
}

export enum DeviceFlowError {
  AUTHORIZATION_PENDING = 'authorization_pending',
  SLOW_DOWN = 'slow_down',
  EXPIRED_TOKEN = 'expired_token',
  ACCESS_DENIED = 'access_denied',
  INVALID_REQUEST = 'invalid_request',
  INVALID_CLIENT = 'invalid_client',
  INVALID_GRANT = 'invalid_grant',
}

export enum DeviceFlowState {
  IDLE = 'idle',
  INITIATING = 'initiating',
  AWAITING_AUTHORIZATION = 'awaiting_authorization',
  POLLING = 'polling',
  SLOW_DOWN = 'slow_down',
  AUTHORIZED = 'authorized',
  EXPIRED = 'expired',
  ERROR = 'error',
}

export interface DeviceFlowStatus {
  state: DeviceFlowState;
  deviceCode?: DeviceCodeResponse;
  tokenResponse?: TokenResponse;
  error?: string;
  nextPollTime?: Date;
  timeRemaining?: number;
}

// Storage keys
const STORAGE_KEYS = {
  ACCESS_TOKEN: '@wearforce/access_token',
  REFRESH_TOKEN: '@wearforce/refresh_token',
  TOKEN_EXPIRY: '@wearforce/token_expiry',
} as const;

export class DeviceAuthService {
  private config: DeviceFlowConfig;
  private pollingTimer?: NodeJS.Timeout;
  private statusCallback?: (status: DeviceFlowStatus) => void;
  private currentStatus: DeviceFlowStatus = { state: DeviceFlowState.IDLE };
  
  constructor(config: DeviceFlowConfig) {
    this.config = {
      clientId: config.clientId,
      baseURL: config.baseURL,
      scope: config.scope || 'openid profile',
    };
  }

  /**
   * Sets the status change callback
   */
  public setStatusCallback(callback: (status: DeviceFlowStatus) => void): void {
    this.statusCallback = callback;
  }

  /**
   * Gets the current status
   */
  public getCurrentStatus(): DeviceFlowStatus {
    return this.currentStatus;
  }

  /**
   * Initiates the device authorization flow
   */
  public async initiateDeviceFlow(): Promise<DeviceCodeResponse> {
    if (this.currentStatus.state !== DeviceFlowState.IDLE) {
      throw new Error('Device flow already in progress');
    }

    this.updateStatus({ state: DeviceFlowState.INITIATING });

    try {
      const deviceCodeResponse = await this.requestDeviceCode();
      
      this.updateStatus({
        state: DeviceFlowState.AWAITING_AUTHORIZATION,
        deviceCode: deviceCodeResponse,
        timeRemaining: deviceCodeResponse.expires_in,
      });

      this.startPolling(deviceCodeResponse);
      return deviceCodeResponse;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Manually polls for token (alternative to automatic polling)
   */
  public async pollForToken(): Promise<TokenResponse> {
    if (!this.currentStatus.deviceCode) {
      throw new Error('No device code available');
    }

    try {
      const tokenResponse = await this.requestToken(this.currentStatus.deviceCode);
      this.handleTokenResponse(tokenResponse, this.currentStatus.deviceCode);
      return tokenResponse;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Resets the device flow
   */
  public resetDeviceFlow(): void {
    this.stopPolling();
    this.updateStatus({ state: DeviceFlowState.IDLE });
  }

  /**
   * Gets stored access token
   */
  public async getStoredAccessToken(): Promise<string | null> {
    try {
      const token = await AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
      const expiry = await AsyncStorage.getItem(STORAGE_KEYS.TOKEN_EXPIRY);
      
      if (token && expiry) {
        const expiryDate = new Date(expiry);
        if (expiryDate > new Date()) {
          return token;
        }
        
        // Token expired, try to refresh
        return await this.refreshTokenIfAvailable();
      }
      
      return null;
    } catch (error) {
      console.error('Error retrieving stored token:', error);
      return null;
    }
  }

  /**
   * Clears stored tokens
   */
  public async clearStoredTokens(): Promise<void> {
    try {
      await AsyncStorage.multiRemove([
        STORAGE_KEYS.ACCESS_TOKEN,
        STORAGE_KEYS.REFRESH_TOKEN,
        STORAGE_KEYS.TOKEN_EXPIRY,
      ]);
    } catch (error) {
      console.error('Error clearing stored tokens:', error);
    }
  }

  /**
   * Checks if device is currently authenticated
   */
  public async isAuthenticated(): Promise<boolean> {
    const token = await this.getStoredAccessToken();
    return token !== null;
  }

  // Private methods

  private async requestDeviceCode(): Promise<DeviceCodeResponse> {
    const response = await fetch(`${this.config.baseURL}/oauth/device_authorization`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        client_id: this.config.clientId,
        scope: this.config.scope || '',
      }),
    });

    if (!response.ok) {
      throw new Error(`Device authorization failed: ${response.status}`);
    }

    return await response.json();
  }

  private async requestToken(deviceCode: DeviceCodeResponse): Promise<TokenResponse> {
    const response = await fetch(`${this.config.baseURL}/oauth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
        device_code: deviceCode.device_code,
        client_id: this.config.clientId,
      }),
    });

    // Both 200 and 400 are valid responses for token polling
    if (!response.ok && response.status !== 400) {
      throw new Error(`Token request failed: ${response.status}`);
    }

    return await response.json();
  }

  private startPolling(deviceCode: DeviceCodeResponse): void {
    const interval = Math.max(deviceCode.interval, 5) * 1000; // Minimum 5 seconds
    
    this.pollingTimer = setInterval(async () => {
      try {
        this.updateStatus({
          ...this.currentStatus,
          state: DeviceFlowState.POLLING,
        });

        const tokenResponse = await this.requestToken(deviceCode);
        this.handleTokenResponse(tokenResponse, deviceCode);
      } catch (error) {
        console.error('Polling error:', error);
        // Continue polling on network errors
      }
    }, interval);

    // Also start countdown timer
    this.startCountdownTimer(deviceCode);
  }

  private startCountdownTimer(deviceCode: DeviceCodeResponse): void {
    const startTime = Date.now();
    const expiresIn = deviceCode.expires_in * 1000;

    const countdownTimer = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, expiresIn - elapsed);
      const timeRemaining = Math.floor(remaining / 1000);

      this.updateStatus({
        ...this.currentStatus,
        timeRemaining,
      });

      if (remaining <= 0) {
        clearInterval(countdownTimer);
        this.handleExpiration();
      }
    }, 1000);
  }

  private handleTokenResponse(tokenResponse: TokenResponse, deviceCode: DeviceCodeResponse): void {
    if (tokenResponse.access_token) {
      // Success
      this.stopPolling();
      this.updateStatus({
        state: DeviceFlowState.AUTHORIZED,
        tokenResponse,
      });
      this.storeTokens(tokenResponse);
    } else if (tokenResponse.error === DeviceFlowError.AUTHORIZATION_PENDING) {
      // Continue polling
      this.updateStatus({
        ...this.currentStatus,
        state: DeviceFlowState.AWAITING_AUTHORIZATION,
      });
    } else if (tokenResponse.error === DeviceFlowError.SLOW_DOWN) {
      // Slow down polling
      this.stopPolling();
      const nextPollTime = new Date(Date.now() + 10000); // 10 seconds
      
      this.updateStatus({
        ...this.currentStatus,
        state: DeviceFlowState.SLOW_DOWN,
        nextPollTime,
      });

      setTimeout(() => {
        this.startSlowPolling(deviceCode);
      }, 10000);
    } else if (tokenResponse.error === DeviceFlowError.EXPIRED_TOKEN) {
      this.stopPolling();
      this.updateStatus({
        state: DeviceFlowState.EXPIRED,
        error: 'Authorization code has expired',
      });
    } else {
      this.stopPolling();
      this.updateStatus({
        state: DeviceFlowState.ERROR,
        error: tokenResponse.error_description || tokenResponse.error || 'Unknown error',
      });
    }
  }

  private startSlowPolling(deviceCode: DeviceCodeResponse): void {
    this.pollingTimer = setInterval(async () => {
      try {
        this.updateStatus({
          ...this.currentStatus,
          state: DeviceFlowState.POLLING,
        });

        const tokenResponse = await this.requestToken(deviceCode);
        this.handleTokenResponse(tokenResponse, deviceCode);
      } catch (error) {
        console.error('Slow polling error:', error);
      }
    }, 10000); // 10 seconds
  }

  private stopPolling(): void {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = undefined;
    }
  }

  private async storeTokens(tokenResponse: TokenResponse): Promise<void> {
    try {
      if (!tokenResponse.access_token) return;

      const expiryDate = new Date();
      if (tokenResponse.expires_in) {
        expiryDate.setSeconds(expiryDate.getSeconds() + tokenResponse.expires_in);
      } else {
        expiryDate.setHours(expiryDate.getHours() + 1); // Default 1 hour
      }

      await AsyncStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, tokenResponse.access_token);
      await AsyncStorage.setItem(STORAGE_KEYS.TOKEN_EXPIRY, expiryDate.toISOString());

      if (tokenResponse.refresh_token) {
        await AsyncStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, tokenResponse.refresh_token);
      }
    } catch (error) {
      console.error('Error storing tokens:', error);
    }
  }

  private async refreshTokenIfAvailable(): Promise<string | null> {
    try {
      const refreshToken = await AsyncStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
      if (!refreshToken) return null;

      const response = await fetch(`${this.config.baseURL}/oauth/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: this.config.clientId,
        }),
      });

      if (!response.ok) {
        await this.clearStoredTokens();
        return null;
      }

      const tokenResponse: TokenResponse = await response.json();
      if (tokenResponse.access_token) {
        await this.storeTokens(tokenResponse);
        return tokenResponse.access_token;
      }

      return null;
    } catch (error) {
      console.error('Error refreshing token:', error);
      return null;
    }
  }

  private handleExpiration(): void {
    this.stopPolling();
    this.updateStatus({
      state: DeviceFlowState.EXPIRED,
      error: 'Device authorization has expired',
    });
  }

  private handleError(error: any): void {
    this.stopPolling();
    const errorMessage = error?.message || 'Unknown error occurred';
    this.updateStatus({
      state: DeviceFlowState.ERROR,
      error: errorMessage,
    });
  }

  private updateStatus(status: Partial<DeviceFlowStatus>): void {
    this.currentStatus = { ...this.currentStatus, ...status };
    if (this.statusCallback) {
      this.statusCallback(this.currentStatus);
    }
  }

  /**
   * Opens the verification URI in the device's browser
   */
  public async openVerificationURI(): Promise<void> {
    if (!this.currentStatus.deviceCode) {
      throw new Error('No device code available');
    }

    const { Linking } = await import('react-native');
    const uri = this.currentStatus.deviceCode.verification_uri_complete ||
                this.currentStatus.deviceCode.verification_uri;

    const canOpen = await Linking.canOpenURL(uri);
    if (canOpen) {
      await Linking.openURL(uri);
    } else {
      throw new Error('Cannot open verification URI');
    }
  }

  /**
   * Copies the user code to clipboard
   */
  public async copyUserCodeToClipboard(): Promise<void> {
    if (!this.currentStatus.deviceCode?.user_code) {
      throw new Error('No user code available');
    }

    const { Clipboard } = await import('react-native');
    await Clipboard.setString(this.currentStatus.deviceCode.user_code);
  }

  /**
   * Shares the verification information
   */
  public async shareVerificationInfo(): Promise<void> {
    if (!this.currentStatus.deviceCode) {
      throw new Error('No device code available');
    }

    const { Share } = await import('react-native');
    const message = `Device Authorization Code: ${this.currentStatus.deviceCode.user_code}\nVisit: ${this.currentStatus.deviceCode.verification_uri}`;

    await Share.share({
      message,
      title: 'WearForce Device Authorization',
      url: this.currentStatus.deviceCode.verification_uri,
    });
  }
}