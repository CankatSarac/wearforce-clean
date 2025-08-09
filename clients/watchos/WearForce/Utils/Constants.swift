import Foundation
import SwiftUI

struct Constants {
    
    // MARK: - API Configuration
    
    struct API {
        static let baseURL = "https://api.wearforce-clean.com"
        static let websocketURL = "wss://api.wearforce-clean.com/ws"
        static let apiVersion = "v1"
        static let timeout: TimeInterval = 30
        static let retryAttempts = 3
        
        struct Endpoints {
            // Authentication
            static let login = "/auth/login"
            static let refresh = "/auth/refresh"
            static let logout = "/auth/logout"
            
            // Chat
            static let chat = "/api/v1/chat"
            static let chatHistory = "/api/v1/chat/history"
            
            // CRM
            static let customers = "/api/v1/crm/customers"
            static let leads = "/api/v1/crm/leads"
            static let opportunities = "/api/v1/crm/opportunities"
            static let activities = "/api/v1/crm/activities"
            
            // ERP
            static let orders = "/api/v1/erp/orders"
            static let inventory = "/api/v1/erp/inventory"
            static let products = "/api/v1/erp/products"
            static let suppliers = "/api/v1/erp/suppliers"
            
            // Dashboard
            static let metrics = "/api/v1/dashboard/metrics"
            static let reports = "/api/v1/dashboard/reports"
            
            // Speech
            static let transcribe = "/api/v1/speech/transcribe"
            static let synthesize = "/api/v1/speech/synthesize"
        }
    }
    
    // MARK: - UserDefaults Keys
    
    struct UserDefaultsKeys {
        static let authToken = "authToken"
        static let refreshToken = "refreshToken"
        static let userId = "userId"
        static let userRole = "userRole"
        static let notificationSettings = "notificationSettings"
        static let conversationHistory = "conversationHistory"
        static let lastSyncTimestamp = "lastSyncTimestamp"
    }
    
    // MARK: - UI Configuration
    
    struct UI {
        // Colors
        struct Colors {
            static let primary = Color.blue
            static let secondary = Color.gray
            static let success = Color.green
            static let warning = Color.orange
            static let error = Color.red
            static let background = Color(.systemBackground)
            static let cardBackground = Color(.secondarySystemBackground)
        }
        
        // Typography
        struct Typography {
            static let titleFont = Font.title2.weight(.bold)
            static let headlineFont = Font.headline.weight(.semibold)
            static let bodyFont = Font.body
            static let captionFont = Font.caption
            static let smallCaptionFont = Font.caption2
        }
        
        // Spacing
        struct Spacing {
            static let extraSmall: CGFloat = 4
            static let small: CGFloat = 8
            static let medium: CGFloat = 16
            static let large: CGFloat = 24
            static let extraLarge: CGFloat = 32
        }
        
        // Corner Radius
        struct CornerRadius {
            static let small: CGFloat = 6
            static let medium: CGFloat = 12
            static let large: CGFloat = 20
        }
        
        // Animation
        struct Animation {
            static let fast = SwiftUI.Animation.easeInOut(duration: 0.2)
            static let medium = SwiftUI.Animation.easeInOut(duration: 0.3)
            static let slow = SwiftUI.Animation.easeInOut(duration: 0.5)
        }
    }
    
    // MARK: - Business Rules
    
    struct Business {
        static let maxMessageLength = 1000
        static let maxRecordingDuration: TimeInterval = 60 // 1 minute
        static let minPasswordLength = 8
        static let sessionTimeout: TimeInterval = 3600 // 1 hour
        static let maxSearchResults = 100
        static let defaultPageSize = 20
        
        // Status Values
        struct Status {
            struct Customer {
                static let active = "active"
                static let inactive = "inactive"
                static let prospect = "prospect"
            }
            
            struct Lead {
                static let new = "new"
                static let contacted = "contacted"
                static let qualified = "qualified"
                static let unqualified = "unqualified"
                static let lost = "lost"
            }
            
            struct Order {
                static let pending = "pending"
                static let processing = "processing"
                static let shipped = "shipped"
                static let delivered = "delivered"
                static let cancelled = "cancelled"
                static let returned = "returned"
            }
        }
    }
    
    // MARK: - Feature Flags
    
    struct FeatureFlags {
        static let enableVoiceCommands = true
        static let enableOfflineMode = true
        static let enablePushNotifications = true
        static let enableAnalytics = true
        static let enableCrashReporting = true
        static let enableBetaFeatures = false
    }
    
    // MARK: - Error Messages
    
    struct ErrorMessages {
        static let networkError = "Network connection error. Please check your internet connection."
        static let authenticationError = "Authentication failed. Please login again."
        static let serverError = "Server error. Please try again later."
        static let validationError = "Please check your input and try again."
        static let permissionError = "Permission denied. Please check your account permissions."
        static let timeoutError = "Request timeout. Please try again."
        static let unknownError = "An unexpected error occurred. Please try again."
        
        // Voice specific
        static let microphonePermissionError = "Microphone access required for voice commands."
        static let speechRecognitionError = "Speech recognition not available."
        static let audioRecordingError = "Unable to record audio. Please try again."
    }
    
    // MARK: - Success Messages
    
    struct SuccessMessages {
        static let dataSaved = "Data saved successfully"
        static let messageSent = "Message sent successfully"
        static let orderCreated = "Order created successfully"
        static let customerAdded = "Customer added successfully"
        static let leadConverted = "Lead converted successfully"
    }
    
    // MARK: - Quick Actions
    
    struct QuickActions {
        static let customerActions = [
            QuickAction(title: "View Customers", systemImage: "person.3", query: "show me all customers"),
            QuickAction(title: "New Customer", systemImage: "person.badge.plus", query: "create new customer"),
            QuickAction(title: "Top Customers", systemImage: "star.fill", query: "show top customers")
        ]
        
        static let orderActions = [
            QuickAction(title: "Recent Orders", systemImage: "box", query: "show recent orders"),
            QuickAction(title: "Pending Orders", systemImage: "clock", query: "show pending orders"),
            QuickAction(title: "New Order", systemImage: "plus.rectangle", query: "create new order")
        ]
        
        static let inventoryActions = [
            QuickAction(title: "Low Stock", systemImage: "exclamationmark.triangle", query: "show low stock items"),
            QuickAction(title: "Inventory List", systemImage: "cube.box", query: "show inventory"),
            QuickAction(title: "Stock Check", systemImage: "magnifyingglass", query: "check stock levels")
        ]
    }
    
    // MARK: - Notification Categories
    
    struct NotificationCategories {
        static let newOrder = "new_order"
        static let lowStock = "low_stock"
        static let customerMessage = "customer_message"
        static let systemAlert = "system_alert"
        static let marketingUpdate = "marketing_update"
    }
}

// MARK: - Supporting Types

struct QuickAction {
    let title: String
    let systemImage: String
    let query: String
}

// MARK: - Device Capabilities

struct DeviceCapabilities {
    static var supportsVoiceRecognition: Bool {
        #if targetEnvironment(simulator)
        return false
        #else
        return true
        #endif
    }
    
    static var supportsHapticFeedback: Bool {
        return true
    }
    
    static var supportsBackgroundAudio: Bool {
        return true
    }
    
    static var maxDisplayLines: Int {
        // Adjust based on watch screen size
        return 3
    }
}

// MARK: - Debug Configuration

#if DEBUG
struct DebugConfig {
    static let enableLogging = true
    static let enableMockData = false
    static let enablePerformanceMonitoring = true
    static let logLevel: LogLevel = .debug
    
    enum LogLevel {
        case debug, info, warning, error
    }
}
#endif