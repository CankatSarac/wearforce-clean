import SwiftUI

struct DeviceAuthView: View {
    @StateObject private var authService = DeviceAuthService()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                switch authService.state {
                case .idle:
                    IdleView()
                
                case .initiating:
                    InitiatingView()
                
                case .awaitingAuthorization(let deviceCode):
                    AwaitingAuthorizationView(deviceCode: deviceCode)
                
                case .polling(let deviceCode):
                    PollingView(deviceCode: deviceCode)
                
                case .slowDown(let deviceCode, let nextPollTime):
                    SlowDownView(deviceCode: deviceCode, nextPollTime: nextPollTime)
                
                case .authorized:
                    AuthorizedView()
                
                case .expired:
                    ExpiredView()
                
                case .error(let message):
                    ErrorView(message: message)
                }
            }
            .padding()
            .navigationTitle("Device Login")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        authService.resetDeviceFlow()
                        dismiss()
                    }
                }
            }
        }
    }
    
    // MARK: - Idle State View
    private func IdleView() -> some View {
        VStack(spacing: 16) {
            Image(systemName: "applewatch")
                .font(.largeTitle)
                .foregroundColor(.blue)
            
            Text("Connect Your Device")
                .font(.headline)
                .multilineTextAlignment(.center)
            
            Text("Authorize this device to access your WearForce account")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Start Authorization") {
                Task {
                    await authService.initiateDeviceFlow()
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(authService.isLoading)
        }
    }
    
    // MARK: - Initiating State View
    private func InitiatingView() -> some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
            
            Text("Initializing...")
                .font(.headline)
            
            Text("Setting up device authorization")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
    }
    
    // MARK: - Awaiting Authorization View
    private func AwaitingAuthorizationView(deviceCode: DeviceCodeResponse) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "qrcode")
                .font(.title)
                .foregroundColor(.blue)
            
            Text("Authorization Code")
                .font(.headline)
            
            // Display user code prominently
            Text(deviceCode.userCode)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.blue)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            
            VStack(spacing: 8) {
                Text("1. Visit:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text(shortURL(deviceCode.verificationURI))
                    .font(.caption2)
                    .fontWeight(.medium)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                
                Text("2. Enter the code above")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Timer display
            TimerView(expiresIn: deviceCode.expiresIn)
            
            Button("Cancel") {
                authService.resetDeviceFlow()
            }
            .font(.caption)
            .foregroundColor(.red)
        }
    }
    
    // MARK: - Polling View
    private func PollingView(deviceCode: DeviceCodeResponse) -> some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
            
            Text("Checking Status...")
                .font(.headline)
            
            Text("Waiting for authorization")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            VStack(spacing: 4) {
                Text("Code: \(deviceCode.userCode)")
                    .font(.caption)
                    .fontWeight(.medium)
                
                TimerView(expiresIn: deviceCode.expiresIn)
            }
        }
    }
    
    // MARK: - Slow Down View
    private func SlowDownView(deviceCode: DeviceCodeResponse, nextPollTime: Date) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "clock")
                .font(.title)
                .foregroundColor(.orange)
            
            Text("Slowing Down")
                .font(.headline)
            
            Text("Checking less frequently to avoid overloading the server")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            VStack(spacing: 4) {
                Text("Code: \(deviceCode.userCode)")
                    .font(.caption)
                    .fontWeight(.medium)
                
                TimerView(expiresIn: deviceCode.expiresIn)
            }
        }
    }
    
    // MARK: - Authorized View
    private func AuthorizedView() -> some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.largeTitle)
                .foregroundColor(.green)
            
            Text("Device Authorized!")
                .font(.headline)
                .foregroundColor(.green)
            
            Text("Your device is now connected to your WearForce account")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Continue") {
                dismiss()
            }
            .buttonStyle(.borderedProminent)
        }
        .onAppear {
            // Auto-dismiss after 3 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                dismiss()
            }
        }
    }
    
    // MARK: - Expired View
    private func ExpiredView() -> some View {
        VStack(spacing: 16) {
            Image(systemName: "clock.badge.xmark")
                .font(.largeTitle)
                .foregroundColor(.red)
            
            Text("Authorization Expired")
                .font(.headline)
                .foregroundColor(.red)
            
            Text("The authorization code has expired. Please start the process again.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Try Again") {
                Task {
                    await authService.initiateDeviceFlow()
                }
            }
            .buttonStyle(.borderedProminent)
            
            Button("Cancel") {
                authService.resetDeviceFlow()
                dismiss()
            }
            .font(.caption)
            .foregroundColor(.red)
        }
    }
    
    // MARK: - Error View
    private func ErrorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.red)
            
            Text("Authorization Error")
                .font(.headline)
                .foregroundColor(.red)
            
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Try Again") {
                Task {
                    await authService.initiateDeviceFlow()
                }
            }
            .buttonStyle(.borderedProminent)
            
            Button("Cancel") {
                authService.resetDeviceFlow()
                dismiss()
            }
            .font(.caption)
            .foregroundColor(.red)
        }
    }
    
    // MARK: - Helper Functions
    private func shortURL(_ url: String) -> String {
        // Extract domain and path for display
        if let urlObj = URL(string: url) {
            if let host = urlObj.host {
                let path = urlObj.path.isEmpty ? "" : urlObj.path
                return "\(host)\(path)"
            }
        }
        return url
    }
}

// MARK: - Timer View
struct TimerView: View {
    let expiresIn: Int
    @State private var timeRemaining: Int
    @State private var timer: Timer?
    
    init(expiresIn: Int) {
        self.expiresIn = expiresIn
        self._timeRemaining = State(initialValue: expiresIn)
    }
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "timer")
                .font(.caption2)
                .foregroundColor(.secondary)
            
            Text(formatTime(timeRemaining))
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
        }
        .onAppear {
            startTimer()
        }
        .onDisappear {
            timer?.invalidate()
        }
    }
    
    private func startTimer() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            if timeRemaining > 0 {
                timeRemaining -= 1
            } else {
                timer?.invalidate()
            }
        }
    }
    
    private func formatTime(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        return String(format: "%02d:%02d", minutes, remainingSeconds)
    }
}

// MARK: - Preview
struct DeviceAuthView_Previews: PreviewProvider {
    static var previews: some View {
        DeviceAuthView()
    }
}