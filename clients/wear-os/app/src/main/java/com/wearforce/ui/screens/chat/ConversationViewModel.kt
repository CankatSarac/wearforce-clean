package com.wearforce.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.wearforce.data.repository.ChatRepository
import com.wearforce.models.ChatMessage
import com.wearforce.services.AudioService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

@HiltViewModel
class ConversationViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
    private val audioService: AudioService
) : ViewModel() {
    
    private val _uiState = MutableStateFlow(ConversationUiState())
    val uiState: StateFlow<ConversationUiState> = _uiState.asStateFlow()
    
    init {
        loadConversationHistory()
        observeAudioService()
    }
    
    private fun observeAudioService() {
        viewModelScope.launch {
            combine(
                audioService.isRecording,
                audioService.audioLevel,
                audioService.transcriptionResult
            ) { isRecording, audioLevel, transcription ->
                _uiState.value = _uiState.value.copy(
                    isRecording = isRecording,
                    audioLevel = audioLevel
                )
                
                // Handle transcription result
                transcription?.let {
                    sendMessage(it)
                    audioService.clearTranscription()
                }
            }
        }
    }
    
    private fun loadConversationHistory() {
        viewModelScope.launch {
            try {
                _uiState.value = _uiState.value.copy(isLoading = true)
                
                val messages = chatRepository.getConversationHistory()
                _uiState.value = _uiState.value.copy(
                    messages = messages,
                    isLoading = false
                )
                
            } catch (e: Exception) {
                Timber.e(e, "Error loading conversation history")
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load conversation history"
                )
            }
        }
    }
    
    fun sendMessage(content: String) {
        if (content.isBlank()) return
        
        viewModelScope.launch {
            try {
                // Add user message immediately
                val userMessage = ChatMessage(
                    content = content,
                    isFromUser = true,
                    timestamp = System.currentTimeMillis()
                )
                
                val currentMessages = _uiState.value.messages.toMutableList()
                currentMessages.add(userMessage)
                
                _uiState.value = _uiState.value.copy(
                    messages = currentMessages,
                    isLoading = true,
                    error = null
                )
                
                // Send message to API
                val response = chatRepository.sendMessage(content)
                
                // Add assistant response
                val assistantMessage = ChatMessage(
                    content = response.content,
                    isFromUser = false,
                    timestamp = response.timestamp
                )
                
                currentMessages.add(assistantMessage)
                
                _uiState.value = _uiState.value.copy(
                    messages = currentMessages,
                    isLoading = false
                )
                
            } catch (e: Exception) {
                Timber.e(e, "Error sending message")
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to send message: ${e.message}"
                )
            }
        }
    }
    
    fun sendQuickMessage(message: String) {
        sendMessage(message)
    }
    
    fun startRecording() {
        viewModelScope.launch {
            try {
                audioService.startRecording()
            } catch (e: Exception) {
                Timber.e(e, "Error starting recording")
                _uiState.value = _uiState.value.copy(
                    error = "Failed to start recording: ${e.message}"
                )
            }
        }
    }
    
    fun stopRecording() {
        viewModelScope.launch {
            try {
                audioService.stopRecording()
            } catch (e: Exception) {
                Timber.e(e, "Error stopping recording")
                _uiState.value = _uiState.value.copy(
                    error = "Failed to stop recording: ${e.message}"
                )
            }
        }
    }
    
    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
    
    override fun onCleared() {
        super.onCleared()
        // Clean up audio service
        viewModelScope.launch {
            if (_uiState.value.isRecording) {
                audioService.stopRecording()
            }
        }
    }
}

data class ConversationUiState(
    val messages: List<ChatMessage> = emptyList(),
    val isLoading: Boolean = false,
    val isRecording: Boolean = false,
    val audioLevel: Float = 0f,
    val error: String? = null
)