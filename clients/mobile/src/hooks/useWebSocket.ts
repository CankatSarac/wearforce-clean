import { useEffect, useRef, useCallback, useState } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { useAppDispatch, useAppSelector } from './redux';
import { chatActions } from '@store/slices/chatSlice';

interface WebSocketMessage {
  type: string;
  content: string;
  timestamp: Date;
  id?: string;
  userId?: string;
  metadata?: Record<string, any>;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  sendMessage: (message: WebSocketMessage) => void;
  connect: () => void;
  disconnect: () => void;
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'error';
}

const WS_BASE_URL = 'wss://api.wearforce.com/ws';
const RECONNECT_INTERVAL = 5000;
const MAX_RECONNECT_ATTEMPTS = 5;
const HEARTBEAT_INTERVAL = 30000;

export const useWebSocket = (): UseWebSocketReturn => {
  const dispatch = useAppDispatch();
  const { accessToken } = useAppSelector(state => state.auth);
  
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const heartbeatIntervalRef = useRef<NodeJS.Timeout>();
  const isManualDisconnect = useRef(false);

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    
    setIsConnected(false);
    setIsConnecting(false);
    setConnectionState('disconnected');
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }

    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'heartbeat',
          timestamp: new Date().toISOString(),
        }));
      }
    }, HEARTBEAT_INTERVAL);
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (isManualDisconnect.current) return;
    
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      console.error('WebSocket: Max reconnection attempts reached');
      setConnectionState('error');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
    console.log(`WebSocket: Scheduling reconnect attempt ${reconnectAttemptsRef.current + 1} in ${delay}ms`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      connect();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (!accessToken) {
      console.warn('WebSocket: No access token available');
      return;
    }

    if (isConnecting || isConnected) {
      console.warn('WebSocket: Already connecting or connected');
      return;
    }

    cleanup();
    setIsConnecting(true);
    setConnectionState('connecting');
    isManualDisconnect.current = false;

    try {
      const wsUrl = `${WS_BASE_URL}?token=${accessToken}&platform=mobile`;
      console.log('WebSocket: Connecting to', wsUrl);
      
      wsRef.current = new WebSocket(wsUrl, undefined, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      wsRef.current.onopen = (event) => {
        console.log('WebSocket: Connected');
        setIsConnected(true);
        setIsConnecting(false);
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;
        startHeartbeat();

        // Send initial connection message
        wsRef.current?.send(JSON.stringify({
          type: 'connection',
          content: 'mobile_client_connected',
          timestamp: new Date().toISOString(),
        }));
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WebSocket: Message received', message);

          // Handle different message types
          switch (message.type) {
            case 'chat':
              dispatch(chatActions.addMessage({
                id: message.id || Date.now().toString(),
                content: message.content,
                isFromUser: false,
                timestamp: new Date(message.timestamp),
                type: 'text',
              }));
              break;
            
            case 'notification':
              // Handle notifications
              break;
            
            case 'heartbeat':
              // Heartbeat response, do nothing
              break;
            
            case 'error':
              console.error('WebSocket: Server error', message.content);
              dispatch(chatActions.setError(message.content));
              break;
            
            default:
              console.log('WebSocket: Unknown message type', message.type);
          }
        } catch (error) {
          console.error('WebSocket: Failed to parse message', error);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log('WebSocket: Disconnected', event.code, event.reason);
        setIsConnected(false);
        setIsConnecting(false);
        
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
        }

        if (!isManualDisconnect.current) {
          setConnectionState('disconnected');
          scheduleReconnect();
        } else {
          setConnectionState('disconnected');
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket: Error', error);
        setIsConnecting(false);
        setConnectionState('error');
      };

    } catch (error) {
      console.error('WebSocket: Connection failed', error);
      setIsConnecting(false);
      setConnectionState('error');
      scheduleReconnect();
    }
  }, [accessToken, cleanup, startHeartbeat, scheduleReconnect, dispatch]);

  const disconnect = useCallback(() => {
    console.log('WebSocket: Manual disconnect');
    isManualDisconnect.current = true;
    cleanup();
  }, [cleanup]);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket: Cannot send message - not connected');
      return;
    }

    const messageToSend = {
      ...message,
      timestamp: message.timestamp || new Date(),
      id: message.id || Date.now().toString(),
    };

    try {
      wsRef.current.send(JSON.stringify(messageToSend));
      console.log('WebSocket: Message sent', messageToSend);
    } catch (error) {
      console.error('WebSocket: Failed to send message', error);
    }
  }, []);

  // Handle app state changes
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === 'active' && accessToken && !isConnected && !isConnecting) {
        console.log('WebSocket: App became active, reconnecting');
        connect();
      } else if (nextAppState === 'background') {
        console.log('WebSocket: App went to background');
        // Keep connection alive for a while in case user comes back quickly
      }
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);

    return () => {
      subscription?.remove();
    };
  }, [accessToken, isConnected, isConnecting, connect]);

  // Auto-connect when token is available
  useEffect(() => {
    if (accessToken && !isConnected && !isConnecting) {
      connect();
    }
  }, [accessToken, isConnected, isConnecting, connect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    isConnected,
    isConnecting,
    connectionState,
    sendMessage,
    connect,
    disconnect,
  };
};