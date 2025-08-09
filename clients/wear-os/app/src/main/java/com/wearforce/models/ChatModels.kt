package com.wearforce.models

import java.util.*

// Chat Models
data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val content: String,
    val isFromUser: Boolean,
    val timestamp: Long = System.currentTimeMillis(),
    val type: MessageType = MessageType.TEXT,
    val metadata: Map<String, String>? = null,
    val audioData: ByteArray? = null,
    val transcription: String? = null,
    val confidence: Float? = null
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (javaClass != other?.javaClass) return false

        other as ChatMessage

        if (id != other.id) return false
        if (content != other.content) return false
        if (isFromUser != other.isFromUser) return false
        if (timestamp != other.timestamp) return false
        if (type != other.type) return false
        if (metadata != other.metadata) return false
        if (audioData != null) {
            if (other.audioData == null) return false
            if (!audioData.contentEquals(other.audioData)) return false
        } else if (other.audioData != null) return false
        if (transcription != other.transcription) return false
        if (confidence != other.confidence) return false

        return true
    }

    override fun hashCode(): Int {
        var result = id.hashCode()
        result = 31 * result + content.hashCode()
        result = 31 * result + isFromUser.hashCode()
        result = 31 * result + timestamp.hashCode()
        result = 31 * result + type.hashCode()
        result = 31 * result + (metadata?.hashCode() ?: 0)
        result = 31 * result + (audioData?.contentHashCode() ?: 0)
        result = 31 * result + (transcription?.hashCode() ?: 0)
        result = 31 * result + (confidence?.hashCode() ?: 0)
        return result
    }
}

enum class MessageType(val value: String) {
    TEXT("text"),
    VOICE("voice"),
    SYSTEM("system"),
    ERROR("error")
}

data class Conversation(
    val id: String,
    val title: String?,
    val messages: List<ChatMessage>,
    val createdAt: Long,
    val updatedAt: Long,
    val isActive: Boolean = true
)

data class QuickAction(
    val id: String,
    val title: String,
    val description: String,
    val action: String,
    val icon: String,
    val category: QuickActionCategory
)

enum class QuickActionCategory(val displayName: String) {
    CRM("CRM"),
    ERP("ERP"),
    GENERAL("General"),
    ANALYTICS("Analytics")
}

// Voice Interaction Models
data class VoiceCommand(
    val command: String,
    val intent: String,
    val confidence: Float,
    val parameters: Map<String, String> = emptyMap()
)

data class VoiceResponse(
    val text: String,
    val audioData: ByteArray? = null,
    val shouldSpeak: Boolean = true,
    val actions: List<ResponseAction> = emptyList()
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (javaClass != other?.javaClass) return false

        other as VoiceResponse

        if (text != other.text) return false
        if (audioData != null) {
            if (other.audioData == null) return false
            if (!audioData.contentEquals(other.audioData)) return false
        } else if (other.audioData != null) return false
        if (shouldSpeak != other.shouldSpeak) return false
        if (actions != other.actions) return false

        return true
    }

    override fun hashCode(): Int {
        var result = text.hashCode()
        result = 31 * result + (audioData?.contentHashCode() ?: 0)
        result = 31 * result + shouldSpeak.hashCode()
        result = 31 * result + actions.hashCode()
        return result
    }
}

data class ResponseAction(
    val type: ActionType,
    val data: Map<String, Any>
)

enum class ActionType(val value: String) {
    NAVIGATE("navigate"),
    SHOW_DATA("show_data"),
    PERFORM_TASK("perform_task"),
    REQUEST_INPUT("request_input")
}

// Business Data Models
data class Customer(
    val id: String,
    val name: String,
    val company: String,
    val email: String,
    val phone: String,
    val status: String,
    val createdAt: Long,
    val updatedAt: Long
)

data class Order(
    val id: String,
    val orderNumber: String,
    val customerId: String,
    val customerName: String,
    val status: String,
    val total: Double,
    val items: List<OrderItem>,
    val createdAt: Long,
    val updatedAt: Long
)

data class OrderItem(
    val id: String,
    val productId: String,
    val name: String,
    val sku: String,
    val quantity: Int,
    val price: Double,
    val total: Double
)

data class Lead(
    val id: String,
    val name: String,
    val company: String?,
    val email: String,
    val phone: String?,
    val source: String,
    val status: String,
    val value: Double,
    val probability: Double,
    val createdAt: Long,
    val updatedAt: Long
)

data class InventoryItem(
    val id: String,
    val sku: String,
    val name: String,
    val category: String?,
    val quantity: Int,
    val price: Double,
    val lowStockThreshold: Int,
    val supplier: String?,
    val location: String?,
    val updatedAt: Long
) {
    val isLowStock: Boolean get() = quantity <= lowStockThreshold
}

// Dashboard Models
data class DashboardData(
    val todaysSales: Double,
    val monthlyRevenue: Double,
    val totalCustomers: Int,
    val activeLeads: Int,
    val pendingOrders: Int,
    val lowStockItems: Int,
    val recentActivities: List<RecentActivity>,
    val updatedAt: Long
)

data class RecentActivity(
    val id: String,
    val title: String,
    val description: String?,
    val type: String,
    val icon: String,
    val timestamp: Long,
    val relatedEntity: String?
)

// Search Models
data class SearchQuery(
    val query: String,
    val filters: Map<String, String> = emptyMap(),
    val category: SearchCategory? = null,
    val limit: Int = 10
)

enum class SearchCategory(val value: String, val displayName: String) {
    ALL("all", "All"),
    CUSTOMERS("customers", "Customers"),
    ORDERS("orders", "Orders"),
    PRODUCTS("products", "Products"),
    LEADS("leads", "Leads")
}

data class SearchResult<T>(
    val items: List<T>,
    val total: Int,
    val hasMore: Boolean,
    val query: String
)

// API Response Models
data class ApiResponse<T>(
    val success: Boolean,
    val data: T?,
    val message: String?,
    val errors: List<ApiError>? = null
)

data class ApiError(
    val code: String,
    val message: String,
    val field: String? = null
)

// Connectivity and Sync Models
data class SyncStatus(
    val lastSyncTime: Long?,
    val pendingActions: Int,
    val isConnected: Boolean,
    val nextSyncTime: Long?
)

data class OfflineAction(
    val id: String,
    val type: String,
    val data: String, // JSON serialized data
    val timestamp: Long,
    val retryCount: Int = 0
)

// Notification Models
data class WearNotification(
    val id: String,
    val title: String,
    val message: String,
    val type: NotificationType,
    val priority: NotificationPriority,
    val timestamp: Long,
    val isRead: Boolean = false,
    val actionData: Map<String, String>? = null
)

enum class NotificationType(val value: String) {
    CHAT("chat"),
    ORDER("order"),
    LEAD("lead"),
    SYSTEM("system"),
    ERROR("error")
}

enum class NotificationPriority(val value: String, val displayName: String) {
    LOW("low", "Low"),
    NORMAL("normal", "Normal"),
    HIGH("high", "High"),
    URGENT("urgent", "Urgent")
}

// Settings Models
data class AppSettings(
    val voiceEnabled: Boolean = true,
    val hapticEnabled: Boolean = true,
    val autoSpeak: Boolean = true,
    val wakeOnRaise: Boolean = false,
    val syncInterval: Long = 300000L, // 5 minutes
    val voiceLanguage: String = "en-US",
    val theme: AppTheme = AppTheme.AUTO
)

enum class AppTheme(val value: String, val displayName: String) {
    LIGHT("light", "Light"),
    DARK("dark", "Dark"),
    AUTO("auto", "Auto")
}

// Extension functions
fun Long.formatTimestamp(): String {
    val now = System.currentTimeMillis()
    val diff = now - this
    
    return when {
        diff < 60000 -> "Just now"
        diff < 3600000 -> "${diff / 60000}m ago"
        diff < 86400000 -> "${diff / 3600000}h ago"
        diff < 604800000 -> "${diff / 86400000}d ago"
        else -> {
            val date = Date(this)
            java.text.SimpleDateFormat("MMM dd", Locale.getDefault()).format(date)
        }
    }
}

fun Double.formatCurrency(): String {
    return java.text.NumberFormat.getCurrencyInstance().format(this)
}

fun String.truncate(maxLength: Int): String {
    return if (length <= maxLength) this else "${take(maxLength - 3)}..."
}