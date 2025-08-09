import SwiftUI

struct ConversationView: View {
    @EnvironmentObject var apiService: APIService
    @EnvironmentObject var audioService: AudioService
    @EnvironmentObject var webSocketService: WebSocketService
    
    @State private var messages: [ChatMessage] = []
    @State private var isRecording = false
    @State private var isListening = false
    @State private var inputText = ""
    
    var body: some View {
        VStack {
            // Messages List
            List(messages) { message in
                MessageBubbleView(message: message)
                    .listRowInsets(EdgeInsets())
            }
            .listStyle(PlainListStyle())
            
            // Input Controls
            VStack(spacing: 12) {
                // Voice Input Button
                Button(action: toggleRecording) {
                    ZStack {
                        Circle()
                            .fill(isRecording ? Color.red : Color.blue)
                            .frame(width: 60, height: 60)
                        
                        Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                            .font(.title2)
                            .foregroundColor(.white)
                    }
                }
                .scaleEffect(isRecording ? 1.1 : 1.0)
                .animation(.easeInOut(duration: 0.1), value: isRecording)
                
                // Quick Actions
                HStack(spacing: 8) {
                    QuickActionButton(title: "Customers", systemImage: "person.3") {
                        sendQuickMessage("Show me customer list")
                    }
                    
                    QuickActionButton(title: "Orders", systemImage: "box") {
                        sendQuickMessage("Show recent orders")
                    }
                    
                    QuickActionButton(title: "Inventory", systemImage: "cube.box") {
                        sendQuickMessage("Check inventory levels")
                    }
                }
            }
            .padding(.horizontal)
        }
        .navigationTitle("Chat")
        .onAppear {
            setupConversation()
        }
        .onReceive(webSocketService.messageReceived) { message in
            handleIncomingMessage(message)
        }
        .onReceive(audioService.transcriptionReceived) { transcription in
            handleTranscription(transcription)
        }
    }
    
    private func toggleRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }
    
    private func startRecording() {
        isRecording = true
        audioService.startRecording()
        
        // Haptic feedback
        WKInterfaceDevice.current().play(.click)
    }
    
    private func stopRecording() {
        isRecording = false
        audioService.stopRecording()
    }
    
    private func sendQuickMessage(_ text: String) {
        let message = ChatMessage(
            id: UUID(),
            content: text,
            isFromUser: true,
            timestamp: Date(),
            type: .text
        )
        
        messages.append(message)
        sendMessageToAPI(text)
        
        // Haptic feedback
        WKInterfaceDevice.current().play(.notification)
    }
    
    private func sendMessageToAPI(_ content: String) {
        Task {
            do {
                let response = try await apiService.sendChatMessage(content)
                await MainActor.run {
                    let responseMessage = ChatMessage(
                        id: UUID(),
                        content: response.content,
                        isFromUser: false,
                        timestamp: Date(),
                        type: .text
                    )
                    messages.append(responseMessage)
                }
            } catch {
                print("Error sending message: \(error)")
            }
        }
    }
    
    private func handleIncomingMessage(_ message: WebSocketMessage) {
        let chatMessage = ChatMessage(
            id: UUID(),
            content: message.content,
            isFromUser: false,
            timestamp: Date(),
            type: .text
        )
        messages.append(chatMessage)
    }
    
    private func handleTranscription(_ transcription: String) {
        sendQuickMessage(transcription)
    }
    
    private func setupConversation() {
        // Load conversation history
        Task {
            do {
                let history = try await apiService.getConversationHistory()
                await MainActor.run {
                    messages = history
                }
            } catch {
                print("Error loading conversation history: \(error)")
            }
        }
    }
}

struct MessageBubbleView: View {
    let message: ChatMessage
    
    var body: some View {
        HStack {
            if message.isFromUser {
                Spacer()
                Text(message.content)
                    .padding(8)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .frame(maxWidth: .infinity * 0.8, alignment: .trailing)
            } else {
                Text(message.content)
                    .padding(8)
                    .background(Color.gray.opacity(0.2))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .frame(maxWidth: .infinity * 0.8, alignment: .leading)
                Spacer()
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 2)
    }
}

struct QuickActionButton: View {
    let title: String
    let systemImage: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: systemImage)
                    .font(.caption)
                Text(title)
                    .font(.caption2)
            }
            .padding(8)
            .background(Color.gray.opacity(0.2))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(PlainButtonStyle())
    }
}