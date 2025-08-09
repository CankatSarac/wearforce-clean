package com.wearforce.services

import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.io.ByteArrayOutputStream
import java.util.*
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.sqrt

@Singleton
class VoiceService @Inject constructor(
    @ApplicationContext private val context: Context
) {
    
    companion object {
        private const val TAG = "VoiceService"
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        private const val BUFFER_SIZE_MULTIPLIER = 2
    }
    
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    
    // Speech Recognition
    private var speechRecognizer: SpeechRecognizer? = null
    private var isListening = false
    
    // Audio Recording
    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    private var recordingBuffer = ByteArrayOutputStream()
    
    // Text-to-Speech
    private var tts: TextToSpeech? = null
    private var isTtsInitialized = false
    
    // State flows
    private val _voiceState = MutableStateFlow(VoiceState.IDLE)
    val voiceState: StateFlow<VoiceState> = _voiceState.asStateFlow()
    
    private val _transcription = MutableSharedFlow<TranscriptionResult>()
    val transcription: SharedFlow<TranscriptionResult> = _transcription.asSharedFlow()
    
    private val _audioLevel = MutableStateFlow(0f)
    val audioLevel: StateFlow<Float> = _audioLevel.asStateFlow()
    
    private val _speechEvents = MutableSharedFlow<SpeechEvent>()
    val speechEvents: SharedFlow<SpeechEvent> = _speechEvents.asSharedFlow()
    
    init {
        initializeTts()
        initializeSpeechRecognizer()
    }
    
    private fun initializeTts() {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val result = tts?.setLanguage(Locale.US)
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    Log.e(TAG, "TTS language not supported")
                } else {
                    isTtsInitialized = true
                    setupTtsListener()
                    Log.d(TAG, "TTS initialized successfully")
                }
            } else {
                Log.e(TAG, "TTS initialization failed")
            }
        }
    }
    
    private fun setupTtsListener() {
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                scope.launch {
                    _speechEvents.emit(SpeechEvent.TtsStarted)
                }
            }
            
            override fun onDone(utteranceId: String?) {
                scope.launch {
                    _speechEvents.emit(SpeechEvent.TtsCompleted)
                }
            }
            
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                scope.launch {
                    _speechEvents.emit(SpeechEvent.TtsError("TTS error"))
                }
            }
            
            override fun onError(utteranceId: String?, errorCode: Int) {
                scope.launch {
                    _speechEvents.emit(SpeechEvent.TtsError("TTS error code: $errorCode"))
                }
            }
        })
    }
    
    private fun initializeSpeechRecognizer() {
        if (SpeechRecognizer.isRecognitionAvailable(context)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
            speechRecognizer?.setRecognitionListener(SpeechRecognitionListener())
            Log.d(TAG, "Speech recognizer initialized")
        } else {
            Log.e(TAG, "Speech recognition not available")
        }
    }
    
    // Voice Recognition Methods
    fun startListening() {
        if (isListening) {
            Log.w(TAG, "Already listening")
            return
        }
        
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        }
        
        speechRecognizer?.startListening(intent)
        isListening = true
        _voiceState.value = VoiceState.LISTENING
        
        scope.launch {
            _speechEvents.emit(SpeechEvent.ListeningStarted)
        }
        
        Log.d(TAG, "Started listening")
    }
    
    fun stopListening() {
        if (!isListening) return
        
        speechRecognizer?.stopListening()
        isListening = false
        _voiceState.value = VoiceState.PROCESSING
        
        Log.d(TAG, "Stopped listening")
    }
    
    fun cancelListening() {
        if (!isListening) return
        
        speechRecognizer?.cancel()
        isListening = false
        _voiceState.value = VoiceState.IDLE
        
        scope.launch {
            _speechEvents.emit(SpeechEvent.ListeningCancelled)
        }
        
        Log.d(TAG, "Cancelled listening")
    }
    
    // Audio Recording Methods
    fun startRecording() {
        if (recordingJob?.isActive == true) {
            Log.w(TAG, "Already recording")
            return
        }
        
        try {
            val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT) * BUFFER_SIZE_MULTIPLIER
            
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                CHANNEL_CONFIG,
                AUDIO_FORMAT,
                bufferSize
            )
            
            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG, "AudioRecord initialization failed")
                return
            }
            
            recordingBuffer.reset()
            audioRecord?.startRecording()
            _voiceState.value = VoiceState.RECORDING
            
            recordingJob = scope.launch(Dispatchers.IO) {
                recordAudio()
            }
            
            scope.launch {
                _speechEvents.emit(SpeechEvent.RecordingStarted)
            }
            
            Log.d(TAG, "Started recording")
        } catch (e: SecurityException) {
            Log.e(TAG, "Recording permission denied", e)
            scope.launch {
                _speechEvents.emit(SpeechEvent.PermissionDenied)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording", e)
            scope.launch {
                _speechEvents.emit(SpeechEvent.RecordingError(e.message ?: "Recording failed"))
            }
        }
    }
    
    fun stopRecording(): ByteArray? {
        recordingJob?.cancel()
        audioRecord?.stop()
        audioRecord?.release()
        audioRecord = null
        
        _voiceState.value = VoiceState.IDLE
        _audioLevel.value = 0f
        
        val audioData = recordingBuffer.toByteArray()
        recordingBuffer.reset()
        
        scope.launch {
            _speechEvents.emit(SpeechEvent.RecordingStopped)
        }
        
        Log.d(TAG, "Stopped recording, captured ${audioData.size} bytes")
        return audioData
    }
    
    private suspend fun recordAudio() {
        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        val buffer = ShortArray(bufferSize)
        
        try {
            while (isActive && audioRecord?.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                val samplesRead = audioRecord?.read(buffer, 0, bufferSize) ?: 0
                
                if (samplesRead > 0) {
                    // Convert to byte array and store
                    val byteBuffer = ByteArray(samplesRead * 2) // 2 bytes per 16-bit sample
                    for (i in 0 until samplesRead) {
                        val sample = buffer[i]
                        byteBuffer[i * 2] = (sample.toInt() and 0xFF).toByte()
                        byteBuffer[i * 2 + 1] = ((sample.toInt() shr 8) and 0xFF).toByte()
                    }
                    recordingBuffer.write(byteBuffer)
                    
                    // Calculate audio level for UI
                    val level = calculateAudioLevel(buffer, samplesRead)
                    _audioLevel.value = level
                }
                
                yield() // Allow cancellation
            }
        } catch (e: Exception) {
            Log.e(TAG, "Recording error", e)
            withContext(Dispatchers.Main) {
                _speechEvents.emit(SpeechEvent.RecordingError(e.message ?: "Recording error"))
            }
        }
    }
    
    private fun calculateAudioLevel(buffer: ShortArray, samplesRead: Int): Float {
        var sum = 0.0
        for (i in 0 until samplesRead) {
            sum += (buffer[i] * buffer[i]).toDouble()
        }
        
        val rms = sqrt(sum / samplesRead)
        val db = 20 * kotlin.math.log10(rms / Short.MAX_VALUE)
        
        // Normalize to 0-1 range
        return ((db + 60) / 60).coerceIn(0.0, 1.0).toFloat()
    }
    
    // Text-to-Speech Methods
    fun speak(text: String, queueMode: Int = TextToSpeech.QUEUE_FLUSH) {
        if (!isTtsInitialized) {
            Log.e(TAG, "TTS not initialized")
            scope.launch {
                _speechEvents.emit(SpeechEvent.TtsError("TTS not initialized"))
            }
            return
        }
        
        val utteranceId = UUID.randomUUID().toString()
        val params = Bundle().apply {
            putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utteranceId)
        }
        
        val result = tts?.speak(text, queueMode, params, utteranceId)
        if (result != TextToSpeech.SUCCESS) {
            Log.e(TAG, "TTS speak failed")
            scope.launch {
                _speechEvents.emit(SpeechEvent.TtsError("Failed to speak"))
            }
        } else {
            Log.d(TAG, "Speaking: $text")
        }
    }
    
    fun stopSpeaking() {
        tts?.stop()
        scope.launch {
            _speechEvents.emit(SpeechEvent.TtsStopped)
        }
    }
    
    fun isSpeaking(): Boolean {
        return tts?.isSpeaking ?: false
    }
    
    // Recognition Listener
    private inner class SpeechRecognitionListener : RecognitionListener {
        
        override fun onReadyForSpeech(params: Bundle?) {
            Log.d(TAG, "Ready for speech")
            scope.launch {
                _speechEvents.emit(SpeechEvent.ReadyForSpeech)
            }
        }
        
        override fun onBeginningOfSpeech() {
            Log.d(TAG, "Beginning of speech")
            _voiceState.value = VoiceState.SPEAKING
            scope.launch {
                _speechEvents.emit(SpeechEvent.SpeechStarted)
            }
        }
        
        override fun onRmsChanged(rmsdB: Float) {
            _audioLevel.value = (rmsdB + 10) / 20 // Normalize roughly to 0-1
        }
        
        override fun onBufferReceived(buffer: ByteArray?) {
            // Optional: handle audio buffer
        }
        
        override fun onEndOfSpeech() {
            Log.d(TAG, "End of speech")
            _voiceState.value = VoiceState.PROCESSING
            scope.launch {
                _speechEvents.emit(SpeechEvent.SpeechEnded)
            }
        }
        
        override fun onError(error: Int) {
            isListening = false
            _voiceState.value = VoiceState.IDLE
            _audioLevel.value = 0f
            
            val errorMessage = when (error) {
                SpeechRecognizer.ERROR_AUDIO -> "Audio recording error"
                SpeechRecognizer.ERROR_CLIENT -> "Client side error"
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Insufficient permissions"
                SpeechRecognizer.ERROR_NETWORK -> "Network error"
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timeout"
                SpeechRecognizer.ERROR_NO_MATCH -> "No speech input matched"
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognition service busy"
                SpeechRecognizer.ERROR_SERVER -> "Server error"
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech input"
                else -> "Unknown error: $error"
            }
            
            Log.e(TAG, "Speech recognition error: $errorMessage")
            scope.launch {
                if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                    _speechEvents.emit(SpeechEvent.PermissionDenied)
                } else {
                    _speechEvents.emit(SpeechEvent.RecognitionError(errorMessage))
                }
            }
        }
        
        override fun onResults(results: Bundle?) {
            isListening = false
            _voiceState.value = VoiceState.IDLE
            _audioLevel.value = 0f
            
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val confidence = results?.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES)
            
            if (!matches.isNullOrEmpty()) {
                val transcriptionResult = TranscriptionResult(
                    text = matches[0],
                    confidence = confidence?.getOrNull(0) ?: 0f,
                    isFinal = true,
                    alternatives = matches.drop(1)
                )
                
                scope.launch {
                    _transcription.emit(transcriptionResult)
                    _speechEvents.emit(SpeechEvent.TranscriptionReceived(transcriptionResult))
                }
                
                Log.d(TAG, "Final transcription: ${matches[0]} (confidence: ${confidence?.getOrNull(0)})")
            }
        }
        
        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            
            if (!matches.isNullOrEmpty()) {
                val transcriptionResult = TranscriptionResult(
                    text = matches[0],
                    confidence = 0f,
                    isFinal = false,
                    alternatives = emptyList()
                )
                
                scope.launch {
                    _transcription.emit(transcriptionResult)
                }
                
                Log.d(TAG, "Partial transcription: ${matches[0]}")
            }
        }
        
        override fun onEvent(eventType: Int, params: Bundle?) {
            Log.d(TAG, "Speech event: $eventType")
        }
    }
    
    fun cleanup() {
        stopListening()
        stopRecording()
        stopSpeaking()
        
        speechRecognizer?.destroy()
        speechRecognizer = null
        
        tts?.shutdown()
        tts = null
        
        scope.cancel()
    }
}

// Data classes and enums
data class TranscriptionResult(
    val text: String,
    val confidence: Float,
    val isFinal: Boolean,
    val alternatives: List<String>
)

enum class VoiceState {
    IDLE,
    LISTENING,
    SPEAKING,
    RECORDING,
    PROCESSING
}

sealed class SpeechEvent {
    object ListeningStarted : SpeechEvent()
    object ListeningCancelled : SpeechEvent()
    object ReadyForSpeech : SpeechEvent()
    object SpeechStarted : SpeechEvent()
    object SpeechEnded : SpeechEvent()
    object RecordingStarted : SpeechEvent()
    object RecordingStopped : SpeechEvent()
    object TtsStarted : SpeechEvent()
    object TtsCompleted : SpeechEvent()
    object TtsStopped : SpeechEvent()
    object PermissionDenied : SpeechEvent()
    
    data class TranscriptionReceived(val result: TranscriptionResult) : SpeechEvent()
    data class RecognitionError(val message: String) : SpeechEvent()
    data class RecordingError(val message: String) : SpeechEvent()
    data class TtsError(val message: String) : SpeechEvent()
}