import Foundation
import Combine

// MARK: - Device Flow Models
struct DeviceCodeResponse: Codable {
    let deviceCode: String
    let userCode: String
    let verificationURI: String
    let verificationURIComplete: String?
    let expiresIn: Int
    let interval: Int
    
    enum CodingKeys: String, CodingKey {
        case deviceCode = "device_code"
        case userCode = "user_code"
        case verificationURI = "verification_uri"
        case verificationURIComplete = "verification_uri_complete"
        case expiresIn = "expires_in"
        case interval = "interval"
    }
}

struct TokenResponse: Codable {
    let accessToken: String?
    let tokenType: String?
    let expiresIn: Int?
    let refreshToken: String?
    let scope: String?
    let error: String?
    let errorDescription: String?
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
        case refreshToken = "refresh_token"
        case scope = "scope"
        case error = "error"
        case errorDescription = "error_description"
    }
    
    var isSuccess: Bool {
        return error == nil && accessToken != nil
    }
    
    var isPending: Bool {
        return error == "authorization_pending"
    }
    
    var isSlowDown: Bool {
        return error == "slow_down"
    }
    
    var isExpired: Bool {
        return error == "expired_token"
    }
}

// MARK: - Device Flow States
enum DeviceFlowState {
    case idle
    case initiating
    case awaitingAuthorization(DeviceCodeResponse)
    case polling(DeviceCodeResponse)
    case slowDown(DeviceCodeResponse, nextPollTime: Date)
    case authorized(TokenResponse)
    case expired
    case error(String)
}

// MARK: - Device Authentication Service
@MainActor
class DeviceAuthService: ObservableObject {
    @Published var state: DeviceFlowState = .idle
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    private let apiService: APIService
    private let clientID = "wearforce-wearables"
    private var pollingTimer: Timer?
    private var cancellables = Set<AnyCancellable>()
    
    init(apiService: APIService = APIService.shared) {
        self.apiService = apiService
    }
    
    deinit {
        stopPolling()
    }
    
    // MARK: - Public Methods
    
    /// Initiates the device authorization flow
    func initiateDeviceFlow() async {
        guard case .idle = state else {
            print("Device flow already in progress")
            return
        }
        
        isLoading = true
        errorMessage = nil
        state = .initiating
        
        do {
            let deviceCodeResponse = try await requestDeviceCode()
            state = .awaitingAuthorization(deviceCodeResponse)
            startPolling(deviceCodeResponse)
        } catch {
            handleError(error)
        }
        
        isLoading = false
    }
    
    /// Resets the device flow to idle state
    func resetDeviceFlow() {
        stopPolling()
        state = .idle
        isLoading = false
        errorMessage = nil
    }
    
    /// Gets the current user code for display
    var userCode: String? {
        switch state {
        case .awaitingAuthorization(let response),
             .polling(let response),
             .slowDown(let response, _):
            return response.userCode
        default:
            return nil
        }
    }
    
    /// Gets the verification URI for display
    var verificationURI: String? {
        switch state {
        case .awaitingAuthorization(let response),
             .polling(let response),
             .slowDown(let response, _):
            return response.verificationURI
        default:
            return nil
        }
    }
    
    /// Gets the access token if authorized
    var accessToken: String? {
        if case .authorized(let tokenResponse) = state {
            return tokenResponse.accessToken
        }
        return nil
    }
    
    // MARK: - Private Methods
    
    private func requestDeviceCode() async throws -> DeviceCodeResponse {
        let url = URL(string: "\(apiService.baseURL)/oauth/device_authorization")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        
        let parameters = [
            "client_id": clientID,
            "scope": "openid profile"
        ]
        
        let formData = parameters
            .map { "\($0.key)=\($0.value.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")" }
            .joined(separator: "&")
        
        request.httpBody = formData.data(using: .utf8)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw DeviceFlowError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw DeviceFlowError.serverError(httpResponse.statusCode)
        }
        
        do {
            return try JSONDecoder().decode(DeviceCodeResponse.self, from: data)
        } catch {
            print("Failed to decode device code response: \(error)")
            throw DeviceFlowError.decodingError
        }
    }
    
    private func pollForToken(_ deviceCodeResponse: DeviceCodeResponse) async throws -> TokenResponse {
        let url = URL(string: "\(apiService.baseURL)/oauth/token")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        
        let parameters = [
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": deviceCodeResponse.deviceCode,
            "client_id": clientID
        ]
        
        let formData = parameters
            .map { "\($0.key)=\($0.value.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")" }
            .joined(separator: "&")
        
        request.httpBody = formData.data(using: .utf8)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw DeviceFlowError.invalidResponse
        }
        
        // Token endpoint can return 400 for pending authorization
        guard [200, 400].contains(httpResponse.statusCode) else {
            throw DeviceFlowError.serverError(httpResponse.statusCode)
        }
        
        do {
            return try JSONDecoder().decode(TokenResponse.self, from: data)
        } catch {
            print("Failed to decode token response: \(error)")
            throw DeviceFlowError.decodingError
        }
    }
    
    private func startPolling(_ deviceCodeResponse: DeviceCodeResponse) {
        let interval = max(deviceCodeResponse.interval, 5) // Minimum 5 seconds
        
        pollingTimer = Timer.scheduledTimer(withTimeInterval: TimeInterval(interval), repeats: true) { _ in
            Task {
                await self.performPoll(deviceCodeResponse)
            }
        }
    }
    
    private func performPoll(_ deviceCodeResponse: DeviceCodeResponse) async {
        do {
            state = .polling(deviceCodeResponse)
            let tokenResponse = try await pollForToken(deviceCodeResponse)
            
            if tokenResponse.isSuccess {
                stopPolling()
                state = .authorized(tokenResponse)
                
                // Store tokens securely
                try await storeTokens(tokenResponse)
                
            } else if tokenResponse.isPending {
                // Continue polling
                state = .awaitingAuthorization(deviceCodeResponse)
                
            } else if tokenResponse.isSlowDown {
                stopPolling()
                let nextPollTime = Date().addingTimeInterval(10) // Slow down to 10 seconds
                state = .slowDown(deviceCodeResponse, nextPollTime: nextPollTime)
                
                // Restart polling with slower interval
                DispatchQueue.main.asyncAfter(deadline: .now() + 10) {
                    self.startSlowPolling(deviceCodeResponse)
                }
                
            } else if tokenResponse.isExpired {
                stopPolling()
                state = .expired
                
            } else {
                stopPolling()
                state = .error(tokenResponse.errorDescription ?? "Unknown error")
            }
            
        } catch {
            print("Polling error: \(error)")
            // Continue polling on network errors
        }
    }
    
    private func startSlowPolling(_ deviceCodeResponse: DeviceCodeResponse) {
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { _ in
            Task {
                await self.performPoll(deviceCodeResponse)
            }
        }
    }
    
    private func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
    }
    
    private func storeTokens(_ tokenResponse: TokenResponse) async throws {
        guard let accessToken = tokenResponse.accessToken else {
            throw DeviceFlowError.missingToken
        }
        
        // Store in Keychain
        try KeychainService.shared.store(accessToken, for: .accessToken)
        
        if let refreshToken = tokenResponse.refreshToken {
            try KeychainService.shared.store(refreshToken, for: .refreshToken)
        }
        
        // Update API service with new token
        apiService.setAccessToken(accessToken)
    }
    
    private func handleError(_ error: Error) {
        stopPolling()
        
        let errorMessage: String
        if let deviceFlowError = error as? DeviceFlowError {
            errorMessage = deviceFlowError.localizedDescription
        } else {
            errorMessage = error.localizedDescription
        }
        
        self.errorMessage = errorMessage
        state = .error(errorMessage)
    }
}

// MARK: - Device Flow Errors
enum DeviceFlowError: Error, LocalizedError {
    case invalidResponse
    case serverError(Int)
    case decodingError
    case missingToken
    case authorizationExpired
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let code):
            return "Server error: \(code)"
        case .decodingError:
            return "Failed to decode server response"
        case .missingToken:
            return "Missing access token in response"
        case .authorizationExpired:
            return "Device authorization has expired"
        }
    }
}

// MARK: - Keychain Service for Token Storage
class KeychainService {
    static let shared = KeychainService()
    private init() {}
    
    enum KeychainKey: String {
        case accessToken = "wearforce.access_token"
        case refreshToken = "wearforce.refresh_token"
    }
    
    func store(_ value: String, for key: KeychainKey) throws {
        let data = value.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecValueData as String: data
        ]
        
        SecItemDelete(query as CFDictionary) // Delete existing item
        
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.storeFailed(status)
        }
    }
    
    func retrieve(for key: KeychainKey) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var dataTypeRef: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &dataTypeRef)
        
        guard status == errSecSuccess else {
            if status == errSecItemNotFound {
                return nil
            }
            throw KeychainError.retrieveFailed(status)
        }
        
        guard let data = dataTypeRef as? Data else {
            throw KeychainError.invalidData
        }
        
        return String(data: data, encoding: .utf8)
    }
    
    func delete(for key: KeychainKey) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.deleteFailed(status)
        }
    }
}

enum KeychainError: Error, LocalizedError {
    case storeFailed(OSStatus)
    case retrieveFailed(OSStatus)
    case deleteFailed(OSStatus)
    case invalidData
    
    var errorDescription: String? {
        switch self {
        case .storeFailed(let status):
            return "Failed to store in keychain: \(status)"
        case .retrieveFailed(let status):
            return "Failed to retrieve from keychain: \(status)"
        case .deleteFailed(let status):
            return "Failed to delete from keychain: \(status)"
        case .invalidData:
            return "Invalid data in keychain"
        }
    }
}