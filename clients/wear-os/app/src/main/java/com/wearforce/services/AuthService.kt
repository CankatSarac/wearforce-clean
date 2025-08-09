package com.wearforce.services

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONObject
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthService @Inject constructor(
    @ApplicationContext private val context: Context
) {
    
    companion object {
        private const val TAG = "AuthService"
        private const val PREFS_NAME = "wearforce_auth"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_USER_DATA = "user_data"
        private const val BASE_URL = "https://api.wearforce.com"
        private const val CLIENT_ID = "wearforce-wearos"
    }
    
    private val client = OkHttpClient()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    
    // Encrypted SharedPreferences
    private val encryptedPrefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        
        EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }
    
    // Authentication state
    private val _authState = MutableStateFlow(AuthState.CHECKING)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()
    
    private val _user = MutableStateFlow<User?>(null)
    val user: StateFlow<User?> = _user.asStateFlow()
    
    private val _deviceFlow = MutableStateFlow<DeviceFlowState?>(null)
    val deviceFlow: StateFlow<DeviceFlowState?> = _deviceFlow.asStateFlow()
    
    private var pollingJob: Job? = null
    
    init {
        checkAuthStatus()
    }
    
    private fun checkAuthStatus() {
        scope.launch {
            try {
                val accessToken = getStoredAccessToken()
                val userData = getStoredUserData()
                
                if (accessToken != null && userData != null) {
                    if (isTokenValid(accessToken)) {
                        _authState.value = AuthState.AUTHENTICATED
                        _user.value = userData
                        Log.d(TAG, "User already authenticated")
                    } else {
                        // Try to refresh token
                        val refreshToken = getStoredRefreshToken()
                        if (refreshToken != null) {
                            refreshTokens(refreshToken)
                        } else {
                            logout()
                        }
                    }
                } else {
                    _authState.value = AuthState.UNAUTHENTICATED
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error checking auth status", e)
                _authState.value = AuthState.UNAUTHENTICATED
            }
        }
    }
    
    // Device Flow Authentication
    fun startDeviceFlow() {
        scope.launch {
            try {
                _authState.value = AuthState.DEVICE_FLOW_STARTING
                
                val deviceCodeResponse = requestDeviceCode()
                _deviceFlow.value = DeviceFlowState(
                    deviceCode = deviceCodeResponse.deviceCode,
                    userCode = deviceCodeResponse.userCode,
                    verificationUri = deviceCodeResponse.verificationUri,
                    interval = deviceCodeResponse.interval,
                    expiresIn = deviceCodeResponse.expiresIn
                )
                
                _authState.value = AuthState.DEVICE_FLOW_PENDING
                startPolling(deviceCodeResponse)
                
                Log.d(TAG, "Device flow started. User code: ${deviceCodeResponse.userCode}")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start device flow", e)
                _authState.value = AuthState.ERROR
            }
        }
    }
    
    private suspend fun requestDeviceCode(): DeviceCodeResponse {
        val requestBody = FormBody.Builder()
            .add("client_id", CLIENT_ID)
            .add("scope", "openid profile")
            .build()
        
        val request = Request.Builder()
            .url("$BASE_URL/oauth/device_authorization")
            .post(requestBody)
            .build()
        
        return withContext(Dispatchers.IO) {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("Failed to request device code: ${response.code}")
                }
                
                val responseBody = response.body?.string() ?: throw IOException("Empty response")
                val json = JSONObject(responseBody)
                
                DeviceCodeResponse(
                    deviceCode = json.getString("device_code"),
                    userCode = json.getString("user_code"),
                    verificationUri = json.getString("verification_uri"),
                    verificationUriComplete = json.optString("verification_uri_complete"),
                    expiresIn = json.getInt("expires_in"),
                    interval = json.getInt("interval")
                )
            }
        }
    }
    
    private fun startPolling(deviceCodeResponse: DeviceCodeResponse) {
        pollingJob?.cancel()
        pollingJob = scope.launch {
            val interval = maxOf(deviceCodeResponse.interval * 1000L, 5000L) // At least 5 seconds
            val startTime = System.currentTimeMillis()
            val timeoutMillis = deviceCodeResponse.expiresIn * 1000L
            
            while (isActive && System.currentTimeMillis() - startTime < timeoutMillis) {
                try {
                    val tokenResponse = pollForToken(deviceCodeResponse.deviceCode)
                    
                    when {
                        tokenResponse.accessToken != null -> {
                            // Success!
                            handleTokenResponse(tokenResponse)
                            break
                        }
                        tokenResponse.error == "authorization_pending" -> {
                            // Continue polling
                            delay(interval)
                        }
                        tokenResponse.error == "slow_down" -> {
                            // Increase polling interval
                            delay(interval + 5000L)
                        }
                        tokenResponse.error == "expired_token" -> {
                            Log.w(TAG, "Device code expired")
                            _authState.value = AuthState.DEVICE_FLOW_EXPIRED
                            break
                        }
                        else -> {
                            Log.e(TAG, "Token polling error: ${tokenResponse.errorDescription}")
                            _authState.value = AuthState.ERROR
                            break
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Polling error", e)
                    // Continue polling unless it's a critical error
                    delay(interval)
                }
            }
            
            if (isActive && _authState.value == AuthState.DEVICE_FLOW_PENDING) {
                Log.w(TAG, "Device flow timeout")
                _authState.value = AuthState.DEVICE_FLOW_EXPIRED
            }
        }
    }
    
    private suspend fun pollForToken(deviceCode: String): TokenResponse {
        val requestBody = FormBody.Builder()
            .add("grant_type", "urn:ietf:params:oauth:grant-type:device_code")
            .add("device_code", deviceCode)
            .add("client_id", CLIENT_ID)
            .build()
        
        val request = Request.Builder()
            .url("$BASE_URL/oauth/token")
            .post(requestBody)
            .build()
        
        return withContext(Dispatchers.IO) {
            client.newCall(request).execute().use { response ->
                val responseBody = response.body?.string() ?: throw IOException("Empty response")
                val json = JSONObject(responseBody)
                
                TokenResponse(
                    accessToken = json.optString("access_token").takeIf { it.isNotEmpty() },
                    refreshToken = json.optString("refresh_token").takeIf { it.isNotEmpty() },
                    tokenType = json.optString("token_type").takeIf { it.isNotEmpty() },
                    expiresIn = json.optInt("expires_in"),
                    scope = json.optString("scope").takeIf { it.isNotEmpty() },
                    error = json.optString("error").takeIf { it.isNotEmpty() },
                    errorDescription = json.optString("error_description").takeIf { it.isNotEmpty() }
                )
            }
        }
    }
    
    private suspend fun handleTokenResponse(tokenResponse: TokenResponse) {
        try {
            // Store tokens securely
            tokenResponse.accessToken?.let { storeAccessToken(it) }
            tokenResponse.refreshToken?.let { storeRefreshToken(it) }
            
            // Get user info
            val user = fetchUserInfo(tokenResponse.accessToken!!)
            storeUserData(user)
            
            _user.value = user
            _authState.value = AuthState.AUTHENTICATED
            _deviceFlow.value = null
            
            Log.d(TAG, "Authentication successful for user: ${user.email}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle token response", e)
            _authState.value = AuthState.ERROR
        }
    }
    
    private suspend fun fetchUserInfo(accessToken: String): User {
        val request = Request.Builder()
            .url("$BASE_URL/api/v1/auth/me")
            .addHeader("Authorization", "Bearer $accessToken")
            .build()
        
        return withContext(Dispatchers.IO) {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("Failed to fetch user info: ${response.code}")
                }
                
                val responseBody = response.body?.string() ?: throw IOException("Empty response")
                val json = JSONObject(responseBody)
                
                User(
                    id = json.getString("id"),
                    email = json.getString("email"),
                    firstName = json.getString("firstName"),
                    lastName = json.getString("lastName"),
                    role = json.getString("role")
                )
            }
        }
    }
    
    private suspend fun refreshTokens(refreshToken: String) {
        try {
            val requestBody = FormBody.Builder()
                .add("grant_type", "refresh_token")
                .add("refresh_token", refreshToken)
                .add("client_id", CLIENT_ID)
                .build()
            
            val request = Request.Builder()
                .url("$BASE_URL/oauth/token")
                .post(requestBody)
                .build()
            
            val tokenResponse = withContext(Dispatchers.IO) {
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        throw IOException("Token refresh failed: ${response.code}")
                    }
                    
                    val responseBody = response.body?.string() ?: throw IOException("Empty response")
                    val json = JSONObject(responseBody)
                    
                    TokenResponse(
                        accessToken = json.optString("access_token").takeIf { it.isNotEmpty() },
                        refreshToken = json.optString("refresh_token").takeIf { it.isNotEmpty() },
                        tokenType = json.optString("token_type").takeIf { it.isNotEmpty() },
                        expiresIn = json.optInt("expires_in"),
                        scope = json.optString("scope").takeIf { it.isNotEmpty() },
                        error = null,
                        errorDescription = null
                    )
                }
            }
            
            if (tokenResponse.accessToken != null) {
                handleTokenResponse(tokenResponse)
                Log.d(TAG, "Tokens refreshed successfully")
            } else {
                logout()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Token refresh failed", e)
            logout()
        }
    }
    
    fun logout() {
        scope.launch {
            try {
                clearStoredCredentials()
                _user.value = null
                _authState.value = AuthState.UNAUTHENTICATED
                _deviceFlow.value = null
                pollingJob?.cancel()
                
                Log.d(TAG, "User logged out")
            } catch (e: Exception) {
                Log.e(TAG, "Logout error", e)
            }
        }
    }
    
    fun getAccessToken(): String? {
        return getStoredAccessToken()
    }
    
    fun cancelDeviceFlow() {
        pollingJob?.cancel()
        _deviceFlow.value = null
        _authState.value = AuthState.UNAUTHENTICATED
    }
    
    // Storage methods
    private fun storeAccessToken(token: String) {
        encryptedPrefs.edit().putString(KEY_ACCESS_TOKEN, token).apply()
    }
    
    private fun storeRefreshToken(token: String) {
        encryptedPrefs.edit().putString(KEY_REFRESH_TOKEN, token).apply()
    }
    
    private fun storeUserData(user: User) {
        val json = JSONObject().apply {
            put("id", user.id)
            put("email", user.email)
            put("firstName", user.firstName)
            put("lastName", user.lastName)
            put("role", user.role)
        }
        encryptedPrefs.edit().putString(KEY_USER_DATA, json.toString()).apply()
    }
    
    private fun getStoredAccessToken(): String? {
        return encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)
    }
    
    private fun getStoredRefreshToken(): String? {
        return encryptedPrefs.getString(KEY_REFRESH_TOKEN, null)
    }
    
    private fun getStoredUserData(): User? {
        val userData = encryptedPrefs.getString(KEY_USER_DATA, null) ?: return null
        
        return try {
            val json = JSONObject(userData)
            User(
                id = json.getString("id"),
                email = json.getString("email"),
                firstName = json.getString("firstName"),
                lastName = json.getString("lastName"),
                role = json.getString("role")
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse stored user data", e)
            null
        }
    }
    
    private fun clearStoredCredentials() {
        encryptedPrefs.edit().clear().apply()
    }
    
    private fun isTokenValid(token: String): Boolean {
        // Simple JWT token validation - check expiration
        return try {
            val parts = token.split(".")
            if (parts.size != 3) return false
            
            val payload = String(android.util.Base64.decode(parts[1], android.util.Base64.URL_SAFE))
            val json = JSONObject(payload)
            val exp = json.getLong("exp")
            
            exp * 1000 > System.currentTimeMillis()
        } catch (e: Exception) {
            false
        }
    }
    
    fun cleanup() {
        pollingJob?.cancel()
        scope.cancel()
    }
}

// Data classes
data class User(
    val id: String,
    val email: String,
    val firstName: String,
    val lastName: String,
    val role: String
) {
    val fullName: String get() = "$firstName $lastName"
}

data class DeviceCodeResponse(
    val deviceCode: String,
    val userCode: String,
    val verificationUri: String,
    val verificationUriComplete: String?,
    val expiresIn: Int,
    val interval: Int
)

data class TokenResponse(
    val accessToken: String?,
    val refreshToken: String?,
    val tokenType: String?,
    val expiresIn: Int?,
    val scope: String?,
    val error: String?,
    val errorDescription: String?
)

data class DeviceFlowState(
    val deviceCode: String,
    val userCode: String,
    val verificationUri: String,
    val interval: Int,
    val expiresIn: Int
)

enum class AuthState {
    CHECKING,
    UNAUTHENTICATED,
    DEVICE_FLOW_STARTING,
    DEVICE_FLOW_PENDING,
    DEVICE_FLOW_EXPIRED,
    AUTHENTICATED,
    ERROR
}