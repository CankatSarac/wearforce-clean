import Foundation
import Speech
import AVFoundation
import Combine

@MainActor
class AudioService: NSObject, ObservableObject {
    @Published var isRecording = false
    @Published var isListening = false
    @Published var transcriptionReceived = PassthroughSubject<String, Never>()
    @Published var audioLevel: Float = 0.0
    
    private var audioEngine: AVAudioEngine?
    private var speechRecognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var audioSession: AVAudioSession = AVAudioSession.sharedInstance()
    
    override init() {
        super.init()
        setupAudio()
        requestPermissions()
    }
    
    // MARK: - Setup
    
    private func setupAudio() {
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
        speechRecognizer?.delegate = self
        
        audioEngine = AVAudioEngine()
        
        do {
            try audioSession.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            print("Audio session setup error: \(error)")
        }
    }
    
    private func requestPermissions() {
        Task {
            // Request speech recognition permission
            let speechStatus = await withCheckedContinuation { continuation in
                SFSpeechRecognizer.requestAuthorization { status in
                    continuation.resume(returning: status)
                }
            }
            
            // Request microphone permission
            let microphoneGranted = await AVAudioApplication.requestRecordPermission()
            
            await MainActor.run {
                print("Speech recognition authorized: \(speechStatus == .authorized)")
                print("Microphone access granted: \(microphoneGranted)")
            }
        }
    }
    
    // MARK: - Recording Control
    
    func startRecording() {
        guard !isRecording else { return }
        
        Task {
            do {
                try await startSpeechRecognition()
                await MainActor.run {
                    isRecording = true
                    isListening = true
                }
            } catch {
                print("Failed to start recording: \(error)")
            }
        }
    }
    
    func stopRecording() {
        guard isRecording else { return }
        
        stopSpeechRecognition()
        isRecording = false
        isListening = false
    }
    
    // MARK: - Speech Recognition
    
    private func startSpeechRecognition() async throws {
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            throw AudioError.recognitionRequestFailed
        }
        
        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.requiresOnDeviceRecognition = false
        
        // Setup audio engine
        guard let audioEngine = audioEngine else {
            throw AudioError.audioEngineFailed
        }
        
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] (buffer, _) in
            self?.recognitionRequest?.append(buffer)
            
            // Calculate audio level for UI feedback
            let level = self?.calculateAudioLevel(from: buffer) ?? 0.0
            DispatchQueue.main.async {
                self?.audioLevel = level
            }
        }
        
        audioEngine.prepare()
        try audioEngine.start()
        
        // Start recognition task
        guard let speechRecognizer = speechRecognizer else {
            throw AudioError.speechRecognizerUnavailable
        }
        
        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self = self else { return }
            
            if let result = result {
                let transcription = result.bestTranscription.formattedString
                
                if result.isFinal {
                    Task { @MainActor in
                        self.transcriptionReceived.send(transcription)
                        self.stopRecording()
                    }
                }
            }
            
            if let error = error {
                print("Speech recognition error: \(error)")
                Task { @MainActor in
                    self.stopRecording()
                }
            }
        }
    }
    
    private func stopSpeechRecognition() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        
        recognitionTask?.cancel()
        recognitionTask = nil
        
        audioLevel = 0.0
    }
    
    // MARK: - Audio Level Calculation
    
    private func calculateAudioLevel(from buffer: AVAudioPCMBuffer) -> Float {
        guard let channelData = buffer.floatChannelData else { return 0.0 }
        
        let channelDataValue = channelData.pointee
        let channelDataValueArray = stride(from: 0, to: Int(buffer.frameLength), by: buffer.stride).map { channelDataValue[$0] }
        
        let rms = sqrt(channelDataValueArray.map { $0 * $0 }.reduce(0, +) / Float(channelDataValueArray.count))
        let avgPower = 20 * log10(rms)
        let normalizedPower = max(0.0, (avgPower + 60) / 60) // Normalize to 0-1 range
        
        return normalizedPower
    }
    
    // MARK: - Text-to-Speech
    
    func speak(text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0
        
        let synthesizer = AVSpeechSynthesizer()
        synthesizer.speak(utterance)
    }
    
    func stopSpeaking() {
        // Stop any ongoing speech synthesis
        AVSpeechSynthesizer().stopSpeaking(at: .immediate)
    }
}

// MARK: - SFSpeechRecognizerDelegate

extension AudioService: SFSpeechRecognizerDelegate {
    func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer, availabilityDidChange available: Bool) {
        DispatchQueue.main.async {
            print("Speech recognizer availability changed: \(available)")
        }
    }
}

// MARK: - Audio Errors

enum AudioError: LocalizedError {
    case recognitionRequestFailed
    case audioEngineFailed
    case speechRecognizerUnavailable
    case permissionDenied
    
    var errorDescription: String? {
        switch self {
        case .recognitionRequestFailed:
            return "Failed to create speech recognition request"
        case .audioEngineFailed:
            return "Audio engine failed to start"
        case .speechRecognizerUnavailable:
            return "Speech recognizer is not available"
        case .permissionDenied:
            return "Microphone or speech recognition permission denied"
        }
    }
}