import Foundation
import Combine

@MainActor
class APIService: ObservableObject {
    private let baseURL = "https://api.wearforce.com"
    private let urlSession = URLSession.shared
    private var authToken: String?
    
    @Published var isAuthenticated = false
    @Published var isLoading = false
    
    init() {
        loadAuthToken()
    }
    
    // MARK: - Authentication
    
    func authenticate(token: String) {
        self.authToken = token
        self.isAuthenticated = true
        saveAuthToken(token)
    }
    
    func logout() {
        self.authToken = nil
        self.isAuthenticated = false
        clearAuthToken()
    }
    
    // MARK: - Chat API
    
    func sendChatMessage(_ content: String) async throws -> ChatResponse {
        guard let token = authToken else {
            throw APIError.notAuthenticated
        }
        
        let request = ChatRequest(content: content, timestamp: Date())
        let data = try JSONEncoder().encode(request)
        
        var urlRequest = URLRequest(url: URL(string: "\(baseURL)/api/v1/chat")!)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.httpBody = data
        
        let (responseData, response) = try await urlSession.data(for: urlRequest)
        
        try validateResponse(response)
        return try JSONDecoder().decode(ChatResponse.self, from: responseData)
    }
    
    func getConversationHistory() async throws -> [ChatMessage] {
        guard let token = authToken else {
            throw APIError.notAuthenticated
        }
        
        var urlRequest = URLRequest(url: URL(string: "\(baseURL)/api/v1/chat/history")!)
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await urlSession.data(for: urlRequest)
        
        try validateResponse(response)
        let historyResponse = try JSONDecoder().decode(ConversationHistoryResponse.self, from: data)
        return historyResponse.messages
    }
    
    // MARK: - CRM API
    
    func getCustomers() async throws -> [Customer] {
        try await fetchData(endpoint: "/api/v1/crm/customers", responseType: CustomersResponse.self).customers
    }
    
    func getLeads() async throws -> [Lead] {
        try await fetchData(endpoint: "/api/v1/crm/leads", responseType: LeadsResponse.self).leads
    }
    
    func getCustomer(id: String) async throws -> Customer {
        try await fetchData(endpoint: "/api/v1/crm/customers/\(id)", responseType: Customer.self)
    }
    
    // MARK: - ERP API
    
    func getOrders() async throws -> [Order] {
        try await fetchData(endpoint: "/api/v1/erp/orders", responseType: OrdersResponse.self).orders
    }
    
    func getInventory() async throws -> [InventoryItem] {
        try await fetchData(endpoint: "/api/v1/erp/inventory", responseType: InventoryResponse.self).items
    }
    
    func getOrder(id: String) async throws -> Order {
        try await fetchData(endpoint: "/api/v1/erp/orders/\(id)", responseType: Order.self)
    }
    
    // MARK: - Dashboard API
    
    func getDashboardMetrics() async throws -> DashboardMetrics {
        try await fetchData(endpoint: "/api/v1/dashboard/metrics", responseType: DashboardMetrics.self)
    }
    
    // MARK: - Generic Fetch Method
    
    private func fetchData<T: Decodable>(endpoint: String, responseType: T.Type) async throws -> T {
        guard let token = authToken else {
            throw APIError.notAuthenticated
        }
        
        var urlRequest = URLRequest(url: URL(string: "\(baseURL)\(endpoint)")!)
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let (data, response) = try await urlSession.data(for: urlRequest)
        
        try validateResponse(response)
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(responseType, from: data)
    }
    
    // MARK: - Helper Methods
    
    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        switch httpResponse.statusCode {
        case 200...299:
            break
        case 401:
            throw APIError.notAuthenticated
        case 403:
            throw APIError.forbidden
        case 404:
            throw APIError.notFound
        case 429:
            throw APIError.rateLimited
        case 500...599:
            throw APIError.serverError
        default:
            throw APIError.unknown
        }
    }
    
    private func loadAuthToken() {
        if let token = UserDefaults.standard.string(forKey: "authToken") {
            self.authToken = token
            self.isAuthenticated = true
        }
    }
    
    private func saveAuthToken(_ token: String) {
        UserDefaults.standard.set(token, forKey: "authToken")
    }
    
    private func clearAuthToken() {
        UserDefaults.standard.removeObject(forKey: "authToken")
    }
}

// MARK: - API Models

struct ChatRequest: Codable {
    let content: String
    let timestamp: Date
}

struct ChatResponse: Codable {
    let content: String
    let timestamp: Date
    let messageId: String
}

struct ConversationHistoryResponse: Codable {
    let messages: [ChatMessage]
}

struct CustomersResponse: Codable {
    let customers: [Customer]
    let total: Int
}

struct LeadsResponse: Codable {
    let leads: [Lead]
    let total: Int
}

struct OrdersResponse: Codable {
    let orders: [Order]
    let total: Int
}

struct InventoryResponse: Codable {
    let items: [InventoryItem]
    let total: Int
}

// MARK: - API Errors

enum APIError: LocalizedError {
    case notAuthenticated
    case forbidden
    case notFound
    case rateLimited
    case serverError
    case invalidResponse
    case unknown
    
    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Authentication required"
        case .forbidden:
            return "Access denied"
        case .notFound:
            return "Resource not found"
        case .rateLimited:
            return "Too many requests"
        case .serverError:
            return "Server error"
        case .invalidResponse:
            return "Invalid response"
        case .unknown:
            return "Unknown error"
        }
    }
}