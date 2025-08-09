import { io, Socket } from 'socket.io-client'

export interface WebSocketEvent {
  type: string
  data: any
  timestamp: string
  userId?: string
  sessionId?: string
}

export interface WebSocketConfig {
  url: string
  options?: {
    autoConnect?: boolean
    reconnection?: boolean
    reconnectionAttempts?: number
    reconnectionDelay?: number
    timeout?: number
  }
}

class WebSocketService {
  private socket: Socket | null = null
  private listeners: Map<string, Set<Function>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private isConnected = false
  private config: WebSocketConfig

  constructor(config: WebSocketConfig) {
    this.config = config
  }

  connect(token?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket?.connected) {
        resolve()
        return
      }

      const socketUrl = this.config.url || import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:3001'
      
      this.socket = io(socketUrl, {
        auth: {
          token: token || localStorage.getItem('accessToken')
        },
        transports: ['websocket', 'polling'],
        autoConnect: this.config.options?.autoConnect ?? true,
        reconnection: this.config.options?.reconnection ?? true,
        reconnectionAttempts: this.config.options?.reconnectionAttempts ?? 5,
        reconnectionDelay: this.config.options?.reconnectionDelay ?? 1000,
        timeout: this.config.options?.timeout ?? 20000,
      })

      this.setupEventListeners()

      this.socket.on('connect', () => {
        console.log('WebSocket connected')
        this.isConnected = true
        this.reconnectAttempts = 0
        this.emit('connection_status', { status: 'connected' })
        resolve()
      })

      this.socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error)
        this.isConnected = false
        this.emit('connection_status', { status: 'error', error: error.message })
        reject(error)
      })

      this.socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason)
        this.isConnected = false
        this.emit('connection_status', { status: 'disconnected', reason })
      })
    })
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
      this.isConnected = false
      this.emit('connection_status', { status: 'disconnected' })
    }
  }

  private setupEventListeners(): void {
    if (!this.socket) return

    // Dashboard real-time updates
    this.socket.on('dashboard:metrics_updated', (data) => {
      this.emit('dashboard:metrics_updated', data)
    })

    this.socket.on('dashboard:new_activity', (data) => {
      this.emit('dashboard:new_activity', data)
    })

    // CRM events
    this.socket.on('crm:customer_created', (data) => {
      this.emit('crm:customer_created', data)
    })

    this.socket.on('crm:customer_updated', (data) => {
      this.emit('crm:customer_updated', data)
    })

    // ERP events
    this.socket.on('erp:order_created', (data) => {
      this.emit('erp:order_created', data)
    })

    this.socket.on('erp:order_status_changed', (data) => {
      this.emit('erp:order_status_changed', data)
    })

    this.socket.on('erp:inventory_updated', (data) => {
      this.emit('erp:inventory_updated', data)
    })

    this.socket.on('erp:low_stock_alert', (data) => {
      this.emit('erp:low_stock_alert', data)
    })

    // Chat events
    this.socket.on('chat:message', (data) => {
      this.emit('chat:message', data)
    })

    this.socket.on('chat:typing', (data) => {
      this.emit('chat:typing', data)
    })

    // System events
    this.socket.on('system:notification', (data) => {
      this.emit('system:notification', data)
    })

    this.socket.on('system:alert', (data) => {
      this.emit('system:alert', data)
    })

    // User events
    this.socket.on('user:session_updated', (data) => {
      this.emit('user:session_updated', data)
    })
  }

  subscribe(eventType: string, callback: Function): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set())
    }
    this.listeners.get(eventType)!.add(callback)

    // Return unsubscribe function
    return () => {
      this.unsubscribe(eventType, callback)
    }
  }

  unsubscribe(eventType: string, callback: Function): void {
    const callbacks = this.listeners.get(eventType)
    if (callbacks) {
      callbacks.delete(callback)
      if (callbacks.size === 0) {
        this.listeners.delete(eventType)
      }
    }
  }

  private emit(eventType: string, data: any): void {
    const callbacks = this.listeners.get(eventType)
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in WebSocket callback for ${eventType}:`, error)
        }
      })
    }
  }

  send(eventType: string, data: any): void {
    if (this.socket?.connected) {
      this.socket.emit(eventType, {
        ...data,
        timestamp: new Date().toISOString(),
      })
    } else {
      console.warn('WebSocket not connected. Cannot send event:', eventType)
    }
  }

  joinRoom(roomId: string): void {
    this.send('join_room', { roomId })
  }

  leaveRoom(roomId: string): void {
    this.send('leave_room', { roomId })
  }

  // Convenience methods for common operations
  subscribeToUserEvents(userId: string): void {
    this.joinRoom(`user:${userId}`)
  }

  subscribeToOrderUpdates(orderId: string): void {
    this.joinRoom(`order:${orderId}`)
  }

  subscribeToInventoryUpdates(): void {
    this.joinRoom('inventory:updates')
  }

  subscribeToDashboardUpdates(): void {
    this.joinRoom('dashboard:updates')
  }

  subscribeToChatRoom(conversationId: string): void {
    this.joinRoom(`chat:${conversationId}`)
  }

  // Status methods
  isSocketConnected(): boolean {
    return this.isConnected && this.socket?.connected === true
  }

  getConnectionStatus(): 'connected' | 'disconnected' | 'connecting' {
    if (this.isConnected && this.socket?.connected) {
      return 'connected'
    }
    if (this.socket && !this.socket.connected) {
      return 'connecting'
    }
    return 'disconnected'
  }

  // Reconnection handling
  forceReconnect(): void {
    if (this.socket) {
      this.socket.disconnect()
      setTimeout(() => {
        this.socket?.connect()
      }, 1000)
    }
  }
}

// Create singleton instance
const webSocketConfig: WebSocketConfig = {
  url: import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:3001',
  options: {
    autoConnect: false, // We'll connect manually after authentication
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    timeout: 20000,
  }
}

export const webSocketService = new WebSocketService(webSocketConfig)

// Hook for React components
export function useWebSocket() {
  return {
    connect: (token?: string) => webSocketService.connect(token),
    disconnect: () => webSocketService.disconnect(),
    subscribe: (eventType: string, callback: Function) => webSocketService.subscribe(eventType, callback),
    unsubscribe: (eventType: string, callback: Function) => webSocketService.unsubscribe(eventType, callback),
    send: (eventType: string, data: any) => webSocketService.send(eventType, data),
    joinRoom: (roomId: string) => webSocketService.joinRoom(roomId),
    leaveRoom: (roomId: string) => webSocketService.leaveRoom(roomId),
    isConnected: () => webSocketService.isSocketConnected(),
    getConnectionStatus: () => webSocketService.getConnectionStatus(),
    forceReconnect: () => webSocketService.forceReconnect(),
  }
}

export default webSocketService