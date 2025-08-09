package proxy

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/auth"
	"github.com/wearforce/gateway/internal/config"
)

// getErrorType classifies error types for logging without exposing sensitive details
func getErrorType(err error) string {
	if err == nil {
		return "unknown"
	}
	
	errMsg := strings.ToLower(err.Error())
	
	switch {
	case strings.Contains(errMsg, "expired"):
		return "token_expired"
	case strings.Contains(errMsg, "invalid"):
		return "token_invalid"
	case strings.Contains(errMsg, "malformed") || strings.Contains(errMsg, "format"):
		return "token_malformed"
	case strings.Contains(errMsg, "signature"):
		return "signature_invalid"
	case strings.Contains(errMsg, "issuer"):
		return "issuer_mismatch"
	case strings.Contains(errMsg, "audience"):
		return "audience_mismatch"
	case strings.Contains(errMsg, "not before"):
		return "token_not_active"
	case strings.Contains(errMsg, "service unavailable"):
		return "auth_service_unavailable"
	default:
		return "token_validation_failed"
	}
}

// WebSocketProxy manages WebSocket connections and proxying
type WebSocketProxy struct {
	config    *config.WebSocketConfig
	logger    *zap.Logger
	upgrader  websocket.Upgrader
	clients   sync.Map // map[string]*Client
	rooms     sync.Map // map[string]*Room
	validator *auth.JWTValidator
}

// Client represents a WebSocket client
type Client struct {
	ID         string
	UserID     string
	Conn       *websocket.Conn
	Send       chan []byte
	Rooms      map[string]bool
	User       *auth.UserContext
	LastPing   time.Time
	Connected  bool
	ctx        context.Context
	cancel     context.CancelFunc
	mutex      sync.RWMutex
}

// Room represents a chat room
type Room struct {
	ID      string
	Clients map[string]*Client
	mutex   sync.RWMutex
}

// Message represents a WebSocket message
type Message struct {
	Type      string                 `json:"type"`
	RoomID    string                 `json:"room_id,omitempty"`
	UserID    string                 `json:"user_id,omitempty"`
	Content   interface{}            `json:"content,omitempty"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// NewWebSocketProxy creates a new WebSocket proxy
func NewWebSocketProxy(
	config *config.WebSocketConfig,
	logger *zap.Logger,
	validator *auth.JWTValidator,
) *WebSocketProxy {
	upgrader := websocket.Upgrader{
		ReadBufferSize:   config.ReadBufferSize,
		WriteBufferSize:  config.WriteBufferSize,
		HandshakeTimeout: config.HandshakeTimeout,
		CheckOrigin: func(r *http.Request) bool {
			return !config.CheckOrigin // Allow all origins if CheckOrigin is false
		},
		Subprotocols: config.Subprotocols,
	}

	return &WebSocketProxy{
		config:    config,
		logger:    logger,
		upgrader:  upgrader,
		validator: validator,
	}
}

// HandleWebSocket handles WebSocket connection upgrade and management
func (p *WebSocketProxy) HandleWebSocket() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Check connection limits
		currentConnections := 0
		p.clients.Range(func(key, value interface{}) bool {
			currentConnections++
			return true
		})

		if currentConnections >= p.config.MaxConnections {
			p.logger.Warn("WebSocket connection limit reached",
				zap.Int("current", currentConnections),
				zap.Int("max", p.config.MaxConnections),
			)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "Connection limit reached",
				"code":  "CONNECTION_LIMIT_REACHED",
			})
			return
		}

		// Authenticate user
		token := c.Query("token")
		if token == "" {
			token = c.GetHeader("Authorization")
		}

		if token == "" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authentication required",
				"code":  "AUTHENTICATION_REQUIRED",
			})
			return
		}

		userCtx, err := p.validator.ValidateToken(token)
		if err != nil {
			p.logger.Warn("WebSocket authentication failed",
				zap.String("error_type", getErrorType(err)),
				zap.String("remote_addr", c.ClientIP()),
			)
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authentication failed",
				"code":  "AUTHENTICATION_FAILED",
			})
			return
		}

		// Check if user already has too many connections
		userConnections := 0
		p.clients.Range(func(key, value interface{}) bool {
			if client, ok := value.(*Client); ok && client.UserID == userCtx.UserID {
				userConnections++
			}
			return true
		})

		maxUserConnections := 5 // Limit per user
		if userConnections >= maxUserConnections {
			p.logger.Warn("User connection limit reached",
				zap.String("user_id", userCtx.UserID),
				zap.Int("user_connections", userConnections),
			)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "Too many connections for user",
				"code":  "USER_CONNECTION_LIMIT",
			})
			return
		}

		// Upgrade connection with timeout
		conn, err := p.upgrader.Upgrade(c.Writer, c.Request, nil)
		if err != nil {
			p.logger.Error("WebSocket upgrade failed", zap.Error(err))
			return
		}

		// Create context for client lifecycle management
		ctx, cancel := context.WithCancel(c.Request.Context())

		// Create client with proper initialization
		client := &Client{
			ID:        generateClientID(),
			UserID:    userCtx.UserID,
			Conn:      conn,
			Send:      make(chan []byte, 256),
			Rooms:     make(map[string]bool),
			User:      userCtx,
			LastPing:  time.Now(),
			Connected: true,
			ctx:       ctx,
			cancel:    cancel,
		}

		// Set connection parameters
		conn.SetCloseHandler(func(code int, text string) error {
			p.logger.Debug("WebSocket close handler triggered",
				zap.String("client_id", client.ID),
				zap.Int("code", code),
				zap.String("text", text),
			)
			return nil
		})

		p.clients.Store(client.ID, client)
		
		p.logger.Info("WebSocket client connected",
			zap.String("client_id", client.ID),
			zap.String("user_id", userCtx.UserID),
			zap.String("remote_addr", c.Request.RemoteAddr),
			zap.Int("total_connections", currentConnections+1),
		)

		// Start goroutines for handling the connection
		go p.handleClientRead(client)
		go p.handleClientWrite(client)

		// Send welcome message
		welcome := Message{
			Type:      "welcome",
			Content:   map[string]string{"client_id": client.ID},
			Timestamp: time.Now(),
		}
		p.sendToClient(client, welcome)
	}
}

// handleClientRead handles reading messages from WebSocket client
func (p *WebSocketProxy) handleClientRead(client *Client) {
	defer func() {
		client.cancel() // Cancel context to stop write goroutine
		p.disconnectClient(client)
	}()

	// Set read deadline and limits
	client.Conn.SetReadDeadline(time.Now().Add(p.config.ReadDeadline))
	client.Conn.SetReadLimit(p.config.MaxMessageSize)
	
	// Set pong handler for heartbeat
	client.Conn.SetPongHandler(func(string) error {
		client.mutex.Lock()
		client.LastPing = time.Now()
		client.mutex.Unlock()
		client.Conn.SetReadDeadline(time.Now().Add(p.config.ReadDeadline))
		return nil
	})

	for {
		select {
		case <-client.ctx.Done():
			// Context cancelled, stop reading
			return
		default:
			// Set read deadline for each message
			client.Conn.SetReadDeadline(time.Now().Add(p.config.ReadDeadline))
			
			_, messageBytes, err := client.Conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure, websocket.CloseNoStatusReceived) {
					p.logger.Warn("WebSocket read error",
						zap.String("client_id", client.ID),
						zap.String("user_id", client.UserID),
						zap.Error(err),
					)
				}
				return
			}

			// Validate message size to prevent DoS
			if len(messageBytes) > int(p.config.MaxMessageSize) {
				p.logger.Warn("Message too large",
					zap.String("client_id", client.ID),
					zap.Int("size", len(messageBytes)),
					zap.Int64("max_size", p.config.MaxMessageSize),
				)
				continue
			}

			// Parse message
			var message Message
			if err := json.Unmarshal(messageBytes, &message); err != nil {
				p.logger.Warn("Failed to parse WebSocket message",
					zap.String("client_id", client.ID),
					zap.Error(err),
				)
				continue
			}

			// Validate message structure
			if message.Type == "" {
				p.logger.Warn("Message missing type field",
					zap.String("client_id", client.ID),
				)
				continue
			}

			// Set message metadata
			message.UserID = client.UserID
			message.Timestamp = time.Now()

			// Handle message based on type
			if err := p.handleMessage(client, &message); err != nil {
				p.logger.Warn("Failed to handle WebSocket message",
					zap.String("client_id", client.ID),
					zap.String("message_type", message.Type),
					zap.Error(err),
				)
			}
		}
	}
}

// handleClientWrite handles writing messages to WebSocket client
func (p *WebSocketProxy) handleClientWrite(client *Client) {
	ticker := time.NewTicker(p.config.PingPeriod)
	defer func() {
		ticker.Stop()
		// Mark client as disconnected
		client.mutex.Lock()
		client.Connected = false
		client.mutex.Unlock()
		// Close connection gracefully
		client.Conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
		client.Conn.Close()
	}()

	for {
		select {
		case <-client.ctx.Done():
			// Context cancelled, stop writing
			return
			
		case message, ok := <-client.Send:
			client.Conn.SetWriteDeadline(time.Now().Add(p.config.WriteDeadline))
			if !ok {
				// Channel closed, send close message and exit
				return
			}

			// Check if client is still connected
			client.mutex.RLock()
			connected := client.Connected
			client.mutex.RUnlock()
			
			if !connected {
				return
			}

			if err := client.Conn.WriteMessage(websocket.TextMessage, message); err != nil {
				p.logger.Warn("WebSocket write error",
					zap.String("client_id", client.ID),
					zap.String("user_id", client.UserID),
					zap.Error(err),
				)
				return
			}

		case <-ticker.C:
			// Send ping to keep connection alive
			client.Conn.SetWriteDeadline(time.Now().Add(p.config.WriteDeadline))
			
			client.mutex.RLock()
			connected := client.Connected
			client.mutex.RUnlock()
			
			if !connected {
				return
			}
			
			if err := client.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				p.logger.Debug("Ping failed, connection likely closed",
					zap.String("client_id", client.ID),
					zap.Error(err),
				)
				return
			}
		}
	}
}

// handleMessage handles different types of WebSocket messages
func (p *WebSocketProxy) handleMessage(client *Client, message *Message) error {
	switch message.Type {
	case "join_room":
		return p.handleJoinRoom(client, message)
	case "leave_room":
		return p.handleLeaveRoom(client, message)
	case "chat_message":
		return p.handleChatMessage(client, message)
	case "typing_start":
		return p.handleTypingStart(client, message)
	case "typing_stop":
		return p.handleTypingStop(client, message)
	case "ping":
		return p.handlePing(client, message)
	default:
		p.logger.Warn("Unknown message type",
			zap.String("client_id", client.ID),
			zap.String("type", message.Type),
		)
		return nil
	}
}

// handleJoinRoom handles joining a room
func (p *WebSocketProxy) handleJoinRoom(client *Client, message *Message) error {
	if message.RoomID == "" {
		return fmt.Errorf("room_id is required")
	}

	// Get or create room
	room := p.getOrCreateRoom(message.RoomID)

	// Add client to room
	room.mutex.Lock()
	room.Clients[client.ID] = client
	room.mutex.Unlock()

	// Add room to client
	client.mutex.Lock()
	client.Rooms[message.RoomID] = true
	client.mutex.Unlock()

	p.logger.Info("Client joined room",
		zap.String("client_id", client.ID),
		zap.String("user_id", client.UserID),
		zap.String("room_id", message.RoomID),
	)

	// Notify other clients in room
	notification := Message{
		Type:   "user_joined",
		RoomID: message.RoomID,
		UserID: client.UserID,
		Content: map[string]interface{}{
			"user_name": client.User.Name,
			"user_id":   client.UserID,
		},
		Timestamp: time.Now(),
	}

	p.broadcastToRoom(message.RoomID, notification, client.ID)

	// Send confirmation to client
	response := Message{
		Type:   "room_joined",
		RoomID: message.RoomID,
		Content: map[string]interface{}{
			"success": true,
			"users":   p.getRoomUsers(message.RoomID),
		},
		Timestamp: time.Now(),
	}

	return p.sendToClient(client, response)
}

// handleLeaveRoom handles leaving a room
func (p *WebSocketProxy) handleLeaveRoom(client *Client, message *Message) error {
	if message.RoomID == "" {
		return fmt.Errorf("room_id is required")
	}

	p.removeClientFromRoom(client, message.RoomID)

	// Notify other clients
	notification := Message{
		Type:   "user_left",
		RoomID: message.RoomID,
		UserID: client.UserID,
		Content: map[string]interface{}{
			"user_name": client.User.Name,
			"user_id":   client.UserID,
		},
		Timestamp: time.Now(),
	}

	p.broadcastToRoom(message.RoomID, notification, client.ID)

	return nil
}

// handleChatMessage handles chat messages
func (p *WebSocketProxy) handleChatMessage(client *Client, message *Message) error {
	if message.RoomID == "" {
		return fmt.Errorf("room_id is required")
	}

	// Validate client is in room
	client.mutex.RLock()
	inRoom := client.Rooms[message.RoomID]
	client.mutex.RUnlock()

	if !inRoom {
		return fmt.Errorf("client not in room")
	}

	// Create chat message
	chatMessage := Message{
		Type:   "chat_message",
		RoomID: message.RoomID,
		UserID: client.UserID,
		Content: map[string]interface{}{
			"text":      message.Content,
			"user_name": client.User.Name,
			"user_id":   client.UserID,
		},
		Timestamp: time.Now(),
	}

	// Broadcast to room
	p.broadcastToRoom(message.RoomID, chatMessage, "")

	p.logger.Debug("Chat message sent",
		zap.String("client_id", client.ID),
		zap.String("room_id", message.RoomID),
	)

	return nil
}

// handleTypingStart handles typing start notifications
func (p *WebSocketProxy) handleTypingStart(client *Client, message *Message) error {
	if message.RoomID == "" {
		return fmt.Errorf("room_id is required")
	}

	typing := Message{
		Type:   "typing_start",
		RoomID: message.RoomID,
		UserID: client.UserID,
		Content: map[string]interface{}{
			"user_name": client.User.Name,
			"user_id":   client.UserID,
		},
		Timestamp: time.Now(),
	}

	p.broadcastToRoom(message.RoomID, typing, client.ID)
	return nil
}

// handleTypingStop handles typing stop notifications
func (p *WebSocketProxy) handleTypingStop(client *Client, message *Message) error {
	if message.RoomID == "" {
		return fmt.Errorf("room_id is required")
	}

	typing := Message{
		Type:   "typing_stop",
		RoomID: message.RoomID,
		UserID: client.UserID,
		Content: map[string]interface{}{
			"user_name": client.User.Name,
			"user_id":   client.UserID,
		},
		Timestamp: time.Now(),
	}

	p.broadcastToRoom(message.RoomID, typing, client.ID)
	return nil
}

// handlePing handles ping messages
func (p *WebSocketProxy) handlePing(client *Client, message *Message) error {
	pong := Message{
		Type:      "pong",
		Timestamp: time.Now(),
	}
	return p.sendToClient(client, pong)
}

// Helper methods

// getOrCreateRoom gets or creates a room
func (p *WebSocketProxy) getOrCreateRoom(roomID string) *Room {
	if room, exists := p.rooms.Load(roomID); exists {
		return room.(*Room)
	}

	room := &Room{
		ID:      roomID,
		Clients: make(map[string]*Client),
	}

	p.rooms.Store(roomID, room)
	return room
}

// removeClientFromRoom removes client from room
func (p *WebSocketProxy) removeClientFromRoom(client *Client, roomID string) {
	if room, exists := p.rooms.Load(roomID); exists {
		r := room.(*Room)
		r.mutex.Lock()
		delete(r.Clients, client.ID)
		isEmpty := len(r.Clients) == 0
		r.mutex.Unlock()

		// Remove room if empty
		if isEmpty {
			p.rooms.Delete(roomID)
		}
	}

	client.mutex.Lock()
	delete(client.Rooms, roomID)
	client.mutex.Unlock()
}

// disconnectClient handles client disconnection with proper cleanup
func (p *WebSocketProxy) disconnectClient(client *Client) {
	// Ensure we only disconnect once
	client.mutex.Lock()
	if !client.Connected {
		client.mutex.Unlock()
		return
	}
	client.Connected = false
	client.mutex.Unlock()

	p.logger.Info("WebSocket client disconnected",
		zap.String("client_id", client.ID),
		zap.String("user_id", client.UserID),
	)

	// Cancel context to stop all goroutines
	if client.cancel != nil {
		client.cancel()
	}

	// Remove from all rooms
	client.mutex.RLock()
	rooms := make([]string, 0, len(client.Rooms))
	for roomID := range client.Rooms {
		rooms = append(rooms, roomID)
	}
	client.mutex.RUnlock()

	for _, roomID := range rooms {
		p.removeClientFromRoom(client, roomID)
		
		// Notify other clients in room
		notification := Message{
			Type:   "user_left",
			RoomID: roomID,
			UserID: client.UserID,
			Content: map[string]interface{}{
				"user_name": client.User.Name,
				"user_id":   client.UserID,
			},
			Timestamp: time.Now(),
		}
		p.broadcastToRoom(roomID, notification, client.ID)
	}

	// Remove from clients map
	p.clients.Delete(client.ID)
	
	// Close send channel if still open
	select {
	case <-client.Send:
		// Channel already closed
	default:
		close(client.Send)
	}

	// Close WebSocket connection
	if client.Conn != nil {
		client.Conn.Close()
	}
}

// sendToClient sends message to a specific client with timeout
func (p *WebSocketProxy) sendToClient(client *Client, message Message) error {
	// Check if client is still connected
	client.mutex.RLock()
	connected := client.Connected
	client.mutex.RUnlock()
	
	if !connected {
		return fmt.Errorf("client disconnected")
	}

	data, err := json.Marshal(message)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	select {
	case client.Send <- data:
		return nil
	case <-client.ctx.Done():
		return fmt.Errorf("client context cancelled")
	case <-time.After(5 * time.Second):
		// Client's send buffer is full or slow, disconnect client
		p.logger.Warn("Client send timeout, disconnecting",
			zap.String("client_id", client.ID),
			zap.String("user_id", client.UserID),
		)
		go p.disconnectClient(client)
		return fmt.Errorf("client send timeout")
	}
}

// broadcastToRoom broadcasts message to all clients in a room
func (p *WebSocketProxy) broadcastToRoom(roomID string, message Message, excludeClientID string) {
	if room, exists := p.rooms.Load(roomID); exists {
		r := room.(*Room)
		r.mutex.RLock()
		defer r.mutex.RUnlock()

		data, err := json.Marshal(message)
		if err != nil {
			p.logger.Error("Failed to marshal broadcast message", zap.Error(err))
			return
		}

		for clientID, client := range r.Clients {
			if clientID == excludeClientID {
				continue
			}

			select {
			case client.Send <- data:
			default:
				// Client's send buffer is full, skip
				p.logger.Warn("Client send buffer full during broadcast",
					zap.String("client_id", clientID),
					zap.String("room_id", roomID),
				)
			}
		}
	}
}

// getRoomUsers gets list of users in a room
func (p *WebSocketProxy) getRoomUsers(roomID string) []map[string]interface{} {
	var users []map[string]interface{}

	if room, exists := p.rooms.Load(roomID); exists {
		r := room.(*Room)
		r.mutex.RLock()
		defer r.mutex.RUnlock()

		for _, client := range r.Clients {
			users = append(users, map[string]interface{}{
				"user_id":   client.UserID,
				"user_name": client.User.Name,
				"client_id": client.ID,
			})
		}
	}

	return users
}

// StartCleanupWorker starts worker to clean up inactive connections
func (p *WebSocketProxy) StartCleanupWorker(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			p.cleanupInactiveClients()
		}
	}
}

// cleanupInactiveClients removes inactive clients
func (p *WebSocketProxy) cleanupInactiveClients() {
	timeout := p.config.PongTimeout
	now := time.Now()

	var inactiveClients []*Client

	p.clients.Range(func(key, value interface{}) bool {
		client := value.(*Client)
		if now.Sub(client.LastPing) > timeout {
			inactiveClients = append(inactiveClients, client)
		}
		return true
	})

	for _, client := range inactiveClients {
		p.logger.Info("Removing inactive WebSocket client",
			zap.String("client_id", client.ID),
			zap.String("user_id", client.UserID),
		)
		p.disconnectClient(client)
	}
}

// GetStats returns WebSocket proxy statistics
func (p *WebSocketProxy) GetStats() map[string]interface{} {
	var clientCount, roomCount int

	p.clients.Range(func(key, value interface{}) bool {
		clientCount++
		return true
	})

	p.rooms.Range(func(key, value interface{}) bool {
		roomCount++
		return true
	})

	return map[string]interface{}{
		"active_clients": clientCount,
		"active_rooms":   roomCount,
		"max_clients":    p.config.MaxConnections,
	}
}

// generateClientID generates unique client ID
func generateClientID() string {
	return fmt.Sprintf("client-%d", time.Now().UnixNano())
}

// Shutdown gracefully shuts down the WebSocket proxy
func (p *WebSocketProxy) Shutdown(ctx context.Context) error {
	p.logger.Info("Starting WebSocket proxy shutdown")

	// Collect all clients
	var clients []*Client
	p.clients.Range(func(key, value interface{}) bool {
		if client, ok := value.(*Client); ok {
			clients = append(clients, client)
		}
		return true
	})

	p.logger.Info("Disconnecting WebSocket clients", zap.Int("count", len(clients)))

	// Disconnect all clients gracefully
	for _, client := range clients {
		go func(c *Client) {
			// Send close message to client
			closeMessage := Message{
				Type:      "server_shutdown",
				Content:   map[string]string{"reason": "Server is shutting down"},
				Timestamp: time.Now(),
			}
			p.sendToClient(c, closeMessage)
			
			// Give client time to process close message
			time.Sleep(1 * time.Second)
			
			// Disconnect client
			p.disconnectClient(c)
		}(client)
	}

	// Wait for shutdown with timeout
	shutdownComplete := make(chan struct{})
	go func() {
		defer close(shutdownComplete)
		
		// Wait for all clients to disconnect
		for {
			count := 0
			p.clients.Range(func(key, value interface{}) bool {
				count++
				return true
			})
			
			if count == 0 {
				break
			}
			
			time.Sleep(100 * time.Millisecond)
		}
	}()

	select {
	case <-shutdownComplete:
		p.logger.Info("WebSocket proxy shutdown completed")
		return nil
	case <-ctx.Done():
		p.logger.Warn("WebSocket proxy shutdown timed out")
		return ctx.Err()
	}
}