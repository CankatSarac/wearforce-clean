import Foundation
import Combine
import GRPC
import NIO
import SwiftProtobuf

@MainActor
class GRPCService: ObservableObject {
    @Published var isConnected = false
    @Published var isStreaming = false
    @Published var connectionStatus: ConnectionStatus = .disconnected
    
    private var eventLoopGroup: EventLoopGroup?
    private var channel: GRPCChannel?
    private var client: ChatServiceAsyncClient?
    private var audioStreamCall: GRPCAsyncBidirectionalStreamingCall<AudioChunk, AudioResponse>?
    private var conversationStreamCall: GRPCAsyncServerStreamingCall<ConversationResponse>?
    
    private let baseURL = "api.wearforce.com"
    private let port = 443
    private var authToken: String?
    
    // Stream publishers
    @Published var audioResponseReceived = PassthroughSubject<AudioResponse, Never>()
    @Published var conversationReceived = PassthroughSubject<ConversationResponse, Never>()
    
    init() {
        setupGRPC()
    }
    
    deinit {
        disconnect()
    }
    
    // MARK: - Setup & Connection Management
    
    private func setupGRPC() {
        eventLoopGroup = MultiThreadedEventLoopGroup(numberOfThreads: 1)
        
        guard let eventLoopGroup = eventLoopGroup else {
            print("gRPC: Failed to create event loop group")
            return
        }
        
        // Configure TLS
        let tlsConfiguration = GRPCTLSConfiguration.makeClientConfigurationBackedByNIOSSL()
        
        // Create channel with TLS
        channel = try? GRPCChannelPool.with(
            target: .hostAndPort(baseURL, port),
            transportSecurity: .tls(tlsConfiguration),
            eventLoopGroup: eventLoopGroup
        )
        
        guard let channel = channel else {
            print("gRPC: Failed to create channel")
            return
        }
        
        // Create client
        client = ChatServiceAsyncClient(channel: channel)
        
        print("gRPC: Service initialized")
    }
    
    func connect(authToken: String) async {
        self.authToken = authToken
        
        guard let client = client else {
            print("gRPC: Client not initialized")
            return
        }
        
        do {
            connectionStatus = .connecting
            
            // Test connection with a health check
            let healthRequest = HealthCheckRequest.with {
                $0.service = "ChatService"
            }
            
            let callOptions = GRPCCallOptions(
                customMetadata: createAuthMetadata(),
                timeLimit: .timeout(.seconds(10))
            )
            
            let healthResponse = try await client.healthCheck(healthRequest, callOptions: callOptions)
            
            if healthResponse.status == .serving {
                connectionStatus = .connected
                isConnected = true
                print("gRPC: Connected successfully")
                
                // Start conversation stream
                await startConversationStream()
            } else {
                throw GRPCError.serviceUnavailable
            }
            
        } catch {
            print("gRPC: Connection failed - \(error)")
            connectionStatus = .disconnected
            isConnected = false
        }
    }
    
    func disconnect() {
        connectionStatus = .disconnecting
        
        // Close streams
        audioStreamCall?.cancel()
        conversationStreamCall?.cancel()
        audioStreamCall = nil
        conversationStreamCall = nil
        
        // Close channel
        channel?.close().whenComplete { _ in
            print("gRPC: Channel closed")
        }
        
        // Shutdown event loop group
        try? eventLoopGroup?.syncShutdownGracefully()
        eventLoopGroup = nil
        
        connectionStatus = .disconnected
        isConnected = false
        isStreaming = false
        
        print("gRPC: Disconnected")
    }
    
    // MARK: - Audio Streaming
    
    func startAudioStream() async {
        guard let client = client, isConnected else {
            print("gRPC: Cannot start audio stream - not connected")
            return
        }
        
        guard audioStreamCall == nil else {
            print("gRPC: Audio stream already active")
            return
        }
        
        do {
            let callOptions = GRPCCallOptions(
                customMetadata: createAuthMetadata(),
                timeLimit: .timeout(.seconds(300)) // 5 minute timeout for streaming
            )
            
            audioStreamCall = client.streamAudio(callOptions: callOptions)
            isStreaming = true
            
            // Start listening for responses
            Task {
                await listenForAudioResponses()
            }
            
            print("gRPC: Audio stream started")
            
        } catch {
            print("gRPC: Failed to start audio stream - \(error)")
        }
    }
    
    func sendAudioChunk(_ audioData: Data) async {
        guard let audioStreamCall = audioStreamCall else {
            print("gRPC: Audio stream not active")
            return
        }
        
        let audioChunk = AudioChunk.with {
            $0.data = audioData
            $0.timestamp = UInt64(Date().timeIntervalSince1970 * 1000) // milliseconds
            $0.format = .pcm16
            $0.sampleRate = 16000
            $0.channels = 1
        }
        
        do {
            try await audioStreamCall.requestStream.send(audioChunk)
        } catch {
            print("gRPC: Failed to send audio chunk - \(error)")
        }
    }
    
    func stopAudioStream() async {
        guard let audioStreamCall = audioStreamCall else {
            return
        }
        
        // Finish sending
        audioStreamCall.requestStream.finish()
        
        // Wait for completion
        do {
            let finalResponse = try await audioStreamCall.response
            print("gRPC: Audio stream completed with response: \(finalResponse)")
        } catch {
            print("gRPC: Audio stream ended with error: \(error)")
        }
        
        self.audioStreamCall = nil
        isStreaming = false
        
        print("gRPC: Audio stream stopped")
    }
    
    private func listenForAudioResponses() async {
        guard let audioStreamCall = audioStreamCall else {
            return
        }
        
        do {
            for try await response in audioStreamCall.responseStream {
                audioResponseReceived.send(response)
            }
        } catch {
            print("gRPC: Audio response stream error - \(error)")
            isStreaming = false
        }
    }
    
    // MARK: - Conversation Streaming
    
    private func startConversationStream() async {
        guard let client = client else {
            return
        }
        
        do {
            let request = ConversationStreamRequest.with {
                $0.userID = authToken ?? ""
                $0.includeHistory = true
                $0.maxMessages = 100
            }
            
            let callOptions = GRPCCallOptions(
                customMetadata: createAuthMetadata(),
                timeLimit: .none // Keep alive indefinitely
            )
            
            conversationStreamCall = client.streamConversation(request, callOptions: callOptions)
            
            // Listen for conversation updates
            Task {
                await listenForConversationUpdates()
            }
            
            print("gRPC: Conversation stream started")
            
        } catch {
            print("gRPC: Failed to start conversation stream - \(error)")
        }
    }
    
    private func listenForConversationUpdates() async {
        guard let conversationStreamCall = conversationStreamCall else {
            return
        }
        
        do {
            for try await response in conversationStreamCall {
                conversationReceived.send(response)
            }
        } catch {
            print("gRPC: Conversation stream error - \(error)")
            // Try to reconnect conversation stream
            await restartConversationStream()
        }
    }
    
    private func restartConversationStream() async {
        conversationStreamCall?.cancel()
        conversationStreamCall = nil
        
        // Wait a bit before reconnecting
        try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
        
        if isConnected {
            await startConversationStream()
        }
    }
    
    // MARK: - Text Chat
    
    func sendTextMessage(_ content: String) async throws -> ChatResponse {
        guard let client = client, isConnected else {
            throw GRPCError.unavailable
        }
        
        let request = ChatRequest.with {
            $0.content = content
            $0.timestamp = UInt64(Date().timeIntervalSince1970 * 1000)
            $0.messageType = .text
            $0.contextType = .watch
        }
        
        let callOptions = GRPCCallOptions(
            customMetadata: createAuthMetadata(),
            timeLimit: .timeout(.seconds(30))
        )
        
        return try await client.sendMessage(request, callOptions: callOptions)
    }
    
    // MARK: - Voice Message
    
    func sendVoiceMessage(_ audioData: Data, transcript: String? = nil) async throws -> ChatResponse {
        guard let client = client, isConnected else {
            throw GRPCError.unavailable
        }
        
        let request = ChatRequest.with {
            $0.content = transcript ?? ""
            $0.audioData = audioData
            $0.timestamp = UInt64(Date().timeIntervalSince1970 * 1000)
            $0.messageType = .voice
            $0.contextType = .watch
        }
        
        let callOptions = GRPCCallOptions(
            customMetadata: createAuthMetadata(),
            timeLimit: .timeout(.seconds(60)) // Longer timeout for voice processing
        )
        
        return try await client.sendMessage(request, callOptions: callOptions)
    }
    
    // MARK: - Helper Methods
    
    private func createAuthMetadata() -> HPACKHeaders {
        var headers = HPACKHeaders()
        if let authToken = authToken {
            headers.add(name: "authorization", value: "Bearer \(authToken)")
        }
        headers.add(name: "client-type", value: "watchos")
        headers.add(name: "client-version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0")
        return headers
    }
}

// MARK: - Connection Status

enum ConnectionStatus {
    case disconnected
    case connecting
    case connected
    case disconnecting
}

// MARK: - gRPC Error Extension

enum GRPCError: LocalizedError {
    case serviceUnavailable
    case unavailable
    case authenticationFailed
    case streamingFailed
    
    var errorDescription: String? {
        switch self {
        case .serviceUnavailable:
            return "Service is currently unavailable"
        case .unavailable:
            return "gRPC service is not available"
        case .authenticationFailed:
            return "Authentication failed"
        case .streamingFailed:
            return "Streaming connection failed"
        }
    }
}

// MARK: - Protocol Buffer Message Definitions
// These would typically be generated from .proto files

struct AudioChunk {
    var data: Data
    var timestamp: UInt64
    var format: AudioFormat
    var sampleRate: Int32
    var channels: Int32
    
    enum AudioFormat {
        case pcm16
        case aac
        case opus
    }
}

extension AudioChunk {
    static func with(_ configure: (inout AudioChunk) -> Void) -> AudioChunk {
        var chunk = AudioChunk(data: Data(), timestamp: 0, format: .pcm16, sampleRate: 16000, channels: 1)
        configure(&chunk)
        return chunk
    }
}

struct AudioResponse {
    var transcription: String
    var confidence: Float
    var isFinal: Bool
    var timestamp: UInt64
    var error: String?
}

struct ConversationResponse {
    var messageID: String
    var content: String
    var messageType: MessageType
    var timestamp: UInt64
    var userID: String?
    var contextData: [String: String]
    
    enum MessageType {
        case text
        case voice
        case system
        case error
    }
}

struct ConversationStreamRequest {
    var userID: String
    var includeHistory: Bool
    var maxMessages: Int32
}

extension ConversationStreamRequest {
    static func with(_ configure: (inout ConversationStreamRequest) -> Void) -> ConversationStreamRequest {
        var request = ConversationStreamRequest(userID: "", includeHistory: false, maxMessages: 50)
        configure(&request)
        return request
    }
}

struct HealthCheckRequest {
    var service: String
}

extension HealthCheckRequest {
    static func with(_ configure: (inout HealthCheckRequest) -> Void) -> HealthCheckRequest {
        var request = HealthCheckRequest(service: "")
        configure(&request)
        return request
    }
}

struct HealthCheckResponse {
    var status: ServingStatus
    
    enum ServingStatus {
        case unknown
        case serving
        case notServing
        case serviceUnknown
    }
}

struct ChatRequest {
    var content: String
    var audioData: Data?
    var timestamp: UInt64
    var messageType: MessageType
    var contextType: ContextType
    
    enum MessageType {
        case text
        case voice
    }
    
    enum ContextType {
        case web
        case mobile
        case watch
        case wearos
    }
}

extension ChatRequest {
    static func with(_ configure: (inout ChatRequest) -> Void) -> ChatRequest {
        var request = ChatRequest(content: "", audioData: nil, timestamp: 0, messageType: .text, contextType: .watch)
        configure(&request)
        return request
    }
}

struct ChatResponse {
    var messageID: String
    var content: String
    var timestamp: UInt64
    var confidence: Float?
    var contextData: [String: String]
}

// MARK: - Async Client Protocol

protocol ChatServiceAsyncClient {
    func healthCheck(_ request: HealthCheckRequest, callOptions: GRPCCallOptions?) async throws -> HealthCheckResponse
    func sendMessage(_ request: ChatRequest, callOptions: GRPCCallOptions?) async throws -> ChatResponse
    func streamAudio(callOptions: GRPCCallOptions?) -> GRPCAsyncBidirectionalStreamingCall<AudioChunk, AudioResponse>
    func streamConversation(_ request: ConversationStreamRequest, callOptions: GRPCCallOptions?) -> GRPCAsyncServerStreamingCall<ConversationResponse>
}

// Mock implementation for development
class MockChatServiceAsyncClient: ChatServiceAsyncClient {
    func healthCheck(_ request: HealthCheckRequest, callOptions: GRPCCallOptions?) async throws -> HealthCheckResponse {
        return HealthCheckResponse(status: .serving)
    }
    
    func sendMessage(_ request: ChatRequest, callOptions: GRPCCallOptions?) async throws -> ChatResponse {
        return ChatResponse(
            messageID: UUID().uuidString,
            content: "Mock response to: \(request.content)",
            timestamp: UInt64(Date().timeIntervalSince1970 * 1000),
            confidence: 0.95,
            contextData: [:]
        )
    }
    
    func streamAudio(callOptions: GRPCCallOptions?) -> GRPCAsyncBidirectionalStreamingCall<AudioChunk, AudioResponse> {
        // Mock implementation - in reality this would be provided by the generated gRPC client
        fatalError("Mock implementation - use real gRPC generated client")
    }
    
    func streamConversation(_ request: ConversationStreamRequest, callOptions: GRPCCallOptions?) -> GRPCAsyncServerStreamingCall<ConversationResponse> {
        // Mock implementation - in reality this would be provided by the generated gRPC client
        fatalError("Mock implementation - use real gRPC generated client")
    }
}