import Foundation
import Combine
import Network

@MainActor
class WebSocketService: NSObject, ObservableObject {
    @Published var isConnected = false
    @Published var connectionStatus: ConnectionStatus = .disconnected
    @Published var messageReceived = PassthroughSubject<WebSocketMessage, Never>()
    
    private var webSocketTask: URLSessionWebSocketTask?
    private var urlSession: URLSession?
    private let baseURL = "wss://api.wearforce.com/ws"
    private var authToken: String?
    private var reconnectAttempts = 0
    private let maxReconnectAttempts = 5
    private var reconnectTimer: Timer?
    
    // Network monitoring
    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "NetworkMonitor")
    
    override init() {
        super.init()
        setupNetworkMonitoring()
    }
    
    deinit {
        disconnect()
        monitor.cancel()
    }
    
    // MARK: - Connection Management
    
    func connect(token: String? = nil) {
        if let token = token {
            self.authToken = token
        }
        
        guard let authToken = self.authToken else {
            print("WebSocket: No auth token available")
            return
        }
        
        guard webSocketTask == nil else {
            print("WebSocket: Already connected or connecting")
            return
        }
        
        connectionStatus = .connecting
        
        var urlComponents = URLComponents(string: baseURL)!
        urlComponents.queryItems = [
            URLQueryItem(name: "token", value: authToken),
            URLQueryItem(name: "platform", value: "watchos")
        ]
        
        guard let url = urlComponents.url else {
            connectionStatus = .disconnected
            return
        }
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        
        urlSession = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
        webSocketTask = urlSession?.webSocketTask(with: request)
        
        webSocketTask?.resume()
        startListening()
        
        print("WebSocket: Connecting to \(url)")
    }
    
    func disconnect() {
        connectionStatus = .disconnecting
        
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        urlSession = nil
        
        reconnectTimer?.invalidate()
        reconnectTimer = nil
        
        connectionStatus = .disconnected
        isConnected = false
        
        print("WebSocket: Disconnected")
    }
    
    // MARK: - Message Handling
    
    func sendMessage(_ message: OutgoingWebSocketMessage) {
        guard let webSocketTask = webSocketTask, isConnected else {
            print("WebSocket: Not connected, cannot send message")
            return
        }
        
        do {
            let data = try JSONEncoder().encode(message)
            let string = String(data: data, encoding: .utf8) ?? ""
            
            webSocketTask.send(.string(string)) { [weak self] error in
                if let error = error {
                    print("WebSocket: Send error - \(error)")
                    Task { @MainActor in
                        self?.handleConnectionError()
                    }
                }
            }
        } catch {
            print("WebSocket: Encoding error - \(error)")
        }
    }
    
    private func startListening() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                Task { @MainActor in
                    self?.handleReceivedMessage(message)
                    self?.startListening() // Continue listening
                }
            case .failure(let error):
                print("WebSocket: Receive error - \(error)")
                Task { @MainActor in
                    self?.handleConnectionError()
                }
            }
        }
    }
    
    private func handleReceivedMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            parseMessage(text)
        case .data(let data):
            if let text = String(data: data, encoding: .utf8) {
                parseMessage(text)
            }
        @unknown default:
            print("WebSocket: Unknown message type received")
        }
    }
    
    private func parseMessage(_ text: String) {
        do {
            let data = text.data(using: .utf8) ?? Data()
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            
            let message = try decoder.decode(WebSocketMessage.self, from: data)
            messageReceived.send(message)
        } catch {
            print("WebSocket: Message parsing error - \(error)")
        }
    }
    
    // MARK: - Connection Status Handling
    
    private func handleConnectionEstablished() {
        isConnected = true
        connectionStatus = .connected
        reconnectAttempts = 0
        
        // Send connection acknowledgment
        let ackMessage = OutgoingWebSocketMessage(
            type: .acknowledge,
            content: "connected",
            timestamp: Date()
        )
        sendMessage(ackMessage)
        
        print("WebSocket: Connected successfully")
    }
    
    private func handleConnectionError() {
        isConnected = false
        connectionStatus = .disconnected
        
        webSocketTask?.cancel()
        webSocketTask = nil
        
        // Attempt reconnection
        attemptReconnection()
    }
    
    private func attemptReconnection() {
        guard reconnectAttempts < maxReconnectAttempts else {
            print("WebSocket: Max reconnection attempts reached")
            return
        }
        
        reconnectAttempts += 1
        let delay = min(pow(2.0, Double(reconnectAttempts)), 30.0) // Exponential backoff, max 30 seconds
        
        print("WebSocket: Attempting reconnection in \(delay) seconds (attempt \(reconnectAttempts)/\(maxReconnectAttempts))")
        
        reconnectTimer?.invalidate()
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.connect()
            }
        }
    }
    
    // MARK: - Network Monitoring
    
    private func setupNetworkMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                if path.status == .satisfied && !self?.isConnected ?? false {
                    // Network is available and we're not connected, attempt to connect
                    self?.connect()
                } else if path.status != .satisfied && self?.isConnected ?? false {
                    // Network is unavailable, disconnect
                    self?.handleConnectionError()
                }
            }
        }
        monitor.start(queue: monitorQueue)
    }
    
    // MARK: - Convenience Methods
    
    func sendChatMessage(_ content: String) {
        let message = OutgoingWebSocketMessage(
            type: .chat,
            content: content,
            timestamp: Date()
        )
        sendMessage(message)
    }
    
    func sendHeartbeat() {
        let message = OutgoingWebSocketMessage(
            type: .heartbeat,
            content: "ping",
            timestamp: Date()
        )
        sendMessage(message)
    }
}

// MARK: - URLSessionWebSocketDelegate

extension WebSocketService: URLSessionWebSocketDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        Task { @MainActor in
            handleConnectionEstablished()
        }
    }
    
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        Task { @MainActor in
            handleConnectionError()
        }
    }
}

// MARK: - Supporting Types

enum ConnectionStatus {
    case disconnected
    case connecting
    case connected
    case disconnecting
}

struct WebSocketMessage: Codable {
    let id: String
    let type: MessageType
    let content: String
    let timestamp: Date
    let metadata: [String: String]?
    
    enum MessageType: String, Codable {
        case chat = "chat"
        case notification = "notification"
        case update = "update"
        case heartbeat = "heartbeat"
        case error = "error"
        case system = "system"
    }
}

struct OutgoingWebSocketMessage: Codable {
    let type: MessageType
    let content: String
    let timestamp: Date
    let metadata: [String: String]?
    
    init(type: MessageType, content: String, timestamp: Date, metadata: [String: String]? = nil) {
        self.type = type
        self.content = content
        self.timestamp = timestamp
        self.metadata = metadata
    }
    
    enum MessageType: String, Codable {
        case chat = "chat"
        case acknowledge = "ack"
        case heartbeat = "heartbeat"
        case subscribe = "subscribe"
        case unsubscribe = "unsubscribe"
    }
}