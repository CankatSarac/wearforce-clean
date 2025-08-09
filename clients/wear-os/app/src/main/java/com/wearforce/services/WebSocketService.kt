package com.wearforce.services

import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton
import java.util.concurrent.TimeUnit

@Singleton
class WebSocketService @Inject constructor() {
    
    companion object {
        private const val TAG = "WebSocketService"
        private const val BASE_URL = "wss://api.wearforce.com/ws"
        private const val RECONNECT_INTERVAL = 5000L // 5 seconds
        private const val MAX_RECONNECT_ATTEMPTS = 5
        private const val HEARTBEAT_INTERVAL = 30000L // 30 seconds
    }
    
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    
    private var webSocket: WebSocket? = null
    private var authToken: String? = null
    private var reconnectAttempts = 0
    private var heartbeatJob: Job? = null
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()
    
    // Connection state
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()
    
    // Messages flow
    private val _messages = MutableSharedFlow<WebSocketMessage>()
    val messages: SharedFlow<WebSocketMessage> = _messages.asSharedFlow()
    
    // Connection events
    private val _connectionEvents = MutableSharedFlow<ConnectionEvent>()
    val connectionEvents: SharedFlow<ConnectionEvent> = _connectionEvents.asSharedFlow()
    
    fun connect(token: String) {
        authToken = token
        performConnection()
    }
    
    fun disconnect() {
        _connectionState.value = ConnectionState.DISCONNECTING
        heartbeatJob?.cancel()
        webSocket?.close(1000, "Normal closure")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
        Log.d(TAG, "Disconnected")
    }
    
    fun sendMessage(content: String, type: MessageType = MessageType.CHAT) {
        if (_connectionState.value != ConnectionState.CONNECTED) {
            Log.w(TAG, "Cannot send message - not connected")
            return
        }
        
        val message = OutgoingMessage(
            type = type.value,
            content = content,
            timestamp = System.currentTimeMillis(),
            metadata = mapOf("platform" to "wearos")
        )
        
        try {
            val json = JSONObject().apply {
                put("type", message.type)
                put("content", message.content)
                put("timestamp", message.timestamp)
                put("metadata", JSONObject(message.metadata))
            }
            
            webSocket?.send(json.toString())
            Log.d(TAG, "Message sent: $content")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send message", e)
        }
    }
    
    fun sendVoiceMessage(audioData: ByteArray, transcript: String? = null) {
        if (_connectionState.value != ConnectionState.CONNECTED) {
            Log.w(TAG, "Cannot send voice message - not connected")
            return
        }
        
        val message = OutgoingMessage(
            type = MessageType.VOICE.value,
            content = transcript ?: "",
            timestamp = System.currentTimeMillis(),
            metadata = mapOf(
                "platform" to "wearos",
                "hasAudio" to "true",
                "audioFormat" to "pcm_16"
            )
        )
        
        try {
            val json = JSONObject().apply {
                put("type", message.type)
                put("content", message.content)
                put("timestamp", message.timestamp)
                put("metadata", JSONObject(message.metadata))
                put("audioData", android.util.Base64.encodeToString(audioData, android.util.Base64.DEFAULT))
            }
            
            webSocket?.send(json.toString())
            Log.d(TAG, "Voice message sent")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send voice message", e)
        }
    }
    
    private fun performConnection() {
        if (authToken == null) {
            Log.e(TAG, "Cannot connect - no auth token")
            return
        }
        
        _connectionState.value = ConnectionState.CONNECTING
        
        val url = "$BASE_URL?token=$authToken&platform=wearos"
        val request = Request.Builder()
            .url(url)
            .addHeader("Authorization", "Bearer $authToken")
            .build()
        
        webSocket = client.newWebSocket(request, WebSocketListener())
    }
    
    private fun scheduleReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            Log.e(TAG, "Max reconnection attempts reached")
            _connectionState.value = ConnectionState.FAILED
            return
        }
        
        reconnectAttempts++
        Log.d(TAG, "Scheduling reconnect attempt $reconnectAttempts in ${RECONNECT_INTERVAL}ms")
        
        scope.launch {
            delay(RECONNECT_INTERVAL * reconnectAttempts) // Exponential backoff
            performConnection()
        }
    }
    
    private fun startHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = scope.launch {
            while (isActive && _connectionState.value == ConnectionState.CONNECTED) {
                try {
                    sendHeartbeat()
                    delay(HEARTBEAT_INTERVAL)
                } catch (e: Exception) {
                    Log.e(TAG, "Heartbeat failed", e)
                    break
                }
            }
        }
    }
    
    private fun sendHeartbeat() {
        val heartbeat = JSONObject().apply {
            put("type", "heartbeat")
            put("timestamp", System.currentTimeMillis())
        }
        webSocket?.send(heartbeat.toString())
    }
    
    private inner class WebSocketListener : okhttp3.WebSocketListener() {
        
        override fun onOpen(webSocket: WebSocket, response: Response) {
            Log.d(TAG, "WebSocket connected")
            _connectionState.value = ConnectionState.CONNECTED
            reconnectAttempts = 0
            startHeartbeat()
            
            scope.launch {
                _connectionEvents.emit(ConnectionEvent.Connected)
            }
        }
        
        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                val json = JSONObject(text)
                val message = WebSocketMessage(
                    id = json.optString("id", ""),
                    type = json.getString("type"),
                    content = json.getString("content"),
                    timestamp = json.getLong("timestamp"),
                    userId = json.optString("userId"),
                    metadata = parseMetadata(json.optJSONObject("metadata"))
                )
                
                scope.launch {
                    _messages.emit(message)
                }
                
                Log.d(TAG, "Message received: ${message.content}")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to parse message", e)
            }
        }
        
        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            Log.d(TAG, "Binary message received: ${bytes.size()} bytes")
            // Handle binary messages if needed
        }
        
        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            Log.d(TAG, "WebSocket closing: $code $reason")
            _connectionState.value = ConnectionState.DISCONNECTING
        }
        
        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            Log.d(TAG, "WebSocket closed: $code $reason")
            _connectionState.value = ConnectionState.DISCONNECTED
            heartbeatJob?.cancel()
            
            scope.launch {
                _connectionEvents.emit(ConnectionEvent.Disconnected(reason))
            }
        }
        
        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.e(TAG, "WebSocket failure", t)
            _connectionState.value = ConnectionState.DISCONNECTED
            heartbeatJob?.cancel()
            
            scope.launch {
                _connectionEvents.emit(ConnectionEvent.Error(t.message ?: "Connection failed"))
            }
            
            // Attempt to reconnect
            scheduleReconnect()
        }
    }
    
    private fun parseMetadata(jsonObject: JSONObject?): Map<String, String> {
        if (jsonObject == null) return emptyMap()
        
        val metadata = mutableMapOf<String, String>()
        val keys = jsonObject.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            metadata[key] = jsonObject.getString(key)
        }
        return metadata
    }
    
    fun cleanup() {
        disconnect()
        scope.cancel()
    }
}

// Data classes
data class WebSocketMessage(
    val id: String,
    val type: String,
    val content: String,
    val timestamp: Long,
    val userId: String?,
    val metadata: Map<String, String>
)

data class OutgoingMessage(
    val type: String,
    val content: String,
    val timestamp: Long,
    val metadata: Map<String, String>
)

// Enums
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    DISCONNECTING,
    FAILED
}

enum class MessageType(val value: String) {
    CHAT("chat"),
    VOICE("voice"),
    HEARTBEAT("heartbeat"),
    SYSTEM("system"),
    ERROR("error")
}

sealed class ConnectionEvent {
    object Connected : ConnectionEvent()
    data class Disconnected(val reason: String) : ConnectionEvent()
    data class Error(val message: String) : ConnectionEvent()
}