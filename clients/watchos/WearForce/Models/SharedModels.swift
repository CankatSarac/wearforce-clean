import Foundation

// MARK: - Chat Models

struct ChatMessage: Identifiable, Codable {
    let id: UUID
    let content: String
    let isFromUser: Bool
    let timestamp: Date
    let type: MessageType
    let metadata: [String: String]?
    
    enum MessageType: String, Codable {
        case text = "text"
        case voice = "voice"
        case system = "system"
        case error = "error"
    }
    
    init(id: UUID = UUID(), content: String, isFromUser: Bool, timestamp: Date, type: MessageType, metadata: [String: String]? = nil) {
        self.id = id
        self.content = content
        self.isFromUser = isFromUser
        self.timestamp = timestamp
        self.type = type
        self.metadata = metadata
    }
}

// MARK: - CRM Models

struct Customer: Identifiable, Codable {
    let id: String
    let name: String
    let company: String
    let email: String
    let phone: String
    let address: String?
    let status: String
    let createdAt: Date
    let updatedAt: Date?
    let tags: [String]?
    let customFields: [String: String]?
}

struct Lead: Identifiable, Codable {
    let id: String
    let name: String
    let company: String?
    let email: String
    let phone: String?
    let source: String
    let status: String
    let value: Double
    let probability: Double
    let notes: String?
    let assignedTo: String?
    let createdAt: Date
    let updatedAt: Date?
}

struct Opportunity: Identifiable, Codable {
    let id: String
    let name: String
    let customerId: String
    let customerName: String
    let value: Double
    let stage: String
    let probability: Double
    let expectedCloseDate: Date?
    let description: String?
    let assignedTo: String?
    let createdAt: Date
    let updatedAt: Date?
}

struct Activity: Identifiable, Codable {
    let id: String
    let type: ActivityType
    let title: String
    let description: String?
    let relatedTo: RelatedEntity
    let completedAt: Date?
    let dueDate: Date?
    let assignedTo: String?
    let createdBy: String
    let createdAt: Date
    
    enum ActivityType: String, Codable {
        case call = "call"
        case email = "email"
        case meeting = "meeting"
        case task = "task"
        case note = "note"
    }
    
    struct RelatedEntity: Codable {
        let type: EntityType
        let id: String
        let name: String
        
        enum EntityType: String, Codable {
            case customer = "customer"
            case lead = "lead"
            case opportunity = "opportunity"
            case order = "order"
        }
    }
}

// MARK: - ERP Models

struct Order: Identifiable, Codable {
    let id: String
    let orderNumber: String
    let customerId: String
    let customerName: String
    let customerEmail: String?
    let status: String
    let total: Double
    let subtotal: Double
    let tax: Double
    let shipping: Double
    let items: [OrderItem]
    let shippingAddress: String?
    let billingAddress: String?
    let notes: String?
    let createdAt: Date
    let updatedAt: Date?
    let shippedAt: Date?
    let deliveredAt: Date?
}

struct OrderItem: Identifiable, Codable {
    let id: String
    let productId: String
    let name: String
    let sku: String
    let quantity: Int
    let price: Double
    let total: Double
}

struct InventoryItem: Identifiable, Codable {
    let id: String
    let sku: String
    let name: String
    let description: String?
    let category: String?
    let price: Double
    let cost: Double?
    let quantity: Int
    let lowStockThreshold: Int
    let unit: String
    let weight: Double?
    let dimensions: Dimensions?
    let supplier: String?
    let location: String?
    let createdAt: Date
    let updatedAt: Date?
    
    struct Dimensions: Codable {
        let length: Double
        let width: Double
        let height: Double
    }
}

struct Product: Identifiable, Codable {
    let id: String
    let sku: String
    let name: String
    let description: String?
    let category: String?
    let price: Double
    let cost: Double?
    let isActive: Bool
    let images: [String]?
    let specifications: [String: String]?
    let tags: [String]?
    let createdAt: Date
    let updatedAt: Date?
}

struct Supplier: Identifiable, Codable {
    let id: String
    let name: String
    let company: String?
    let email: String
    let phone: String
    let address: String?
    let contactPerson: String?
    let paymentTerms: String?
    let rating: Double?
    let isActive: Bool
    let createdAt: Date
    let updatedAt: Date?
}

// MARK: - Dashboard Models

struct DashboardMetrics: Codable {
    let todaysSales: Double
    let monthlyRevenue: Double
    let totalCustomers: Int
    let activeLeads: Int
    let openLeads: Int
    let pendingOrders: Int
    let lowStockItems: Int
    let recentActivities: [RecentActivity]
    let salesTrend: [SalesTrendPoint]
    let topProducts: [ProductSummary]
    let updatedAt: Date
}

struct RecentActivity: Identifiable, Codable {
    let id: String
    let title: String
    let description: String?
    let type: String
    let icon: String
    let timestamp: Date
    let relatedEntity: String?
}

struct SalesTrendPoint: Codable {
    let date: Date
    let value: Double
    let orders: Int
}

struct ProductSummary: Identifiable, Codable {
    let id: String
    let name: String
    let revenue: Double
    let unitsSold: Int
    let growthRate: Double
}

// MARK: - User Models

struct User: Identifiable, Codable {
    let id: String
    let email: String
    let firstName: String
    let lastName: String
    let role: UserRole
    let permissions: [Permission]
    let isActive: Bool
    let lastLoginAt: Date?
    let createdAt: Date
    let updatedAt: Date?
    
    var fullName: String {
        "\(firstName) \(lastName)"
    }
}

enum UserRole: String, Codable {
    case admin = "admin"
    case manager = "manager"
    case sales = "sales"
    case support = "support"
    case viewer = "viewer"
}

struct Permission: Codable {
    let resource: String
    let actions: [String]
}

// MARK: - Notification Models

struct NotificationSettings: Codable {
    let pushEnabled: Bool
    let emailEnabled: Bool
    let smsEnabled: Bool
    let quietHours: QuietHours?
    let categories: [NotificationCategory]
}

struct QuietHours: Codable {
    let start: String // HH:mm format
    let end: String   // HH:mm format
    let timezone: String
}

struct NotificationCategory: Codable {
    let name: String
    let enabled: Bool
    let priority: Priority
    
    enum Priority: String, Codable {
        case low = "low"
        case medium = "medium"
        case high = "high"
        case urgent = "urgent"
    }
}

// MARK: - API Response Models

struct APIResponse<T: Codable>: Codable {
    let success: Bool
    let data: T?
    let message: String?
    let errors: [APIError]?
    let metadata: APIMetadata?
}

struct APIError: Codable {
    let code: String
    let message: String
    let field: String?
}

struct APIMetadata: Codable {
    let page: Int?
    let limit: Int?
    let total: Int?
    let totalPages: Int?
    let requestId: String
    let timestamp: Date
}

// MARK: - Search Models

struct SearchRequest: Codable {
    let query: String
    let filters: [SearchFilter]?
    let sortBy: String?
    let sortOrder: SortOrder?
    let page: Int?
    let limit: Int?
    
    enum SortOrder: String, Codable {
        case asc = "asc"
        case desc = "desc"
    }
}

struct SearchFilter: Codable {
    let field: String
    let operator: FilterOperator
    let value: String
    
    enum FilterOperator: String, Codable {
        case equals = "eq"
        case notEquals = "ne"
        case contains = "contains"
        case startsWith = "starts_with"
        case greaterThan = "gt"
        case lessThan = "lt"
        case greaterThanOrEqual = "gte"
        case lessThanOrEqual = "lte"
        case between = "between"
        case isNull = "is_null"
        case isNotNull = "is_not_null"
    }
}

struct SearchResult<T: Codable>: Codable {
    let items: [T]
    let total: Int
    let page: Int
    let limit: Int
    let totalPages: Int
    let hasNext: Bool
    let hasPrevious: Bool
}

// MARK: - Extensions

extension Date {
    var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: self, relativeTo: Date())
    }
}

extension Double {
    var currencyFormatted: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.locale = Locale.current
        return formatter.string(from: NSNumber(value: self)) ?? "$0.00"
    }
}

extension String {
    var initials: String {
        let names = self.split(separator: " ")
        let initials = names.compactMap { $0.first }.map { String($0) }
        return initials.joined().uppercased()
    }
}