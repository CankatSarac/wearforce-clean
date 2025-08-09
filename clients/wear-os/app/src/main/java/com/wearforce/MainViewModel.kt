package com.wearforce

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.wearforce.data.repository.AuthRepository
import com.wearforce.data.repository.WebSocketRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val webSocketRepository: WebSocketRepository
) : ViewModel() {
    
    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()
    
    private val _isAuthenticated = MutableStateFlow(false)
    val isAuthenticated: StateFlow<Boolean> = _isAuthenticated.asStateFlow()
    
    init {
        checkAuthenticationStatus()
    }
    
    private fun checkAuthenticationStatus() {
        viewModelScope.launch {
            try {
                _isLoading.value = true
                
                val hasValidToken = authRepository.hasValidToken()
                _isAuthenticated.value = hasValidToken
                
                if (hasValidToken) {
                    // Connect WebSocket if authenticated
                    webSocketRepository.connect()
                }
                
            } catch (e: Exception) {
                Timber.e(e, "Error checking authentication status")
                _isAuthenticated.value = false
            } finally {
                _isLoading.value = false
            }
        }
    }
    
    fun authenticate(token: String) {
        viewModelScope.launch {
            try {
                authRepository.saveToken(token)
                webSocketRepository.connect()
                _isAuthenticated.value = true
            } catch (e: Exception) {
                Timber.e(e, "Error during authentication")
            }
        }
    }
    
    fun logout() {
        viewModelScope.launch {
            try {
                webSocketRepository.disconnect()
                authRepository.clearToken()
                _isAuthenticated.value = false
            } catch (e: Exception) {
                Timber.e(e, "Error during logout")
            }
        }
    }
}