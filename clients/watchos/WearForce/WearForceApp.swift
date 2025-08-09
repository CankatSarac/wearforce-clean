import SwiftUI
import WatchConnectivity

@main
struct WearForceCleanApp: App {
    @StateObject private var apiService = APIService()
    @StateObject private var audioService = AudioService()
    @StateObject private var webSocketService = WebSocketService()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(apiService)
                .environmentObject(audioService)
                .environmentObject(webSocketService)
                .onAppear {
                    setupServices()
                }
        }
    }
    
    private func setupServices() {
        // Initialize WebSocket connection
        webSocketService.connect()
        
        // Setup Watch Connectivity
        if WCSession.isSupported() {
            let session = WCSession.default
            session.activate()
        }
    }
}