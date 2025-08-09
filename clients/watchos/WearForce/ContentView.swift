import SwiftUI

struct ContentView: View {
    @EnvironmentObject var apiService: APIService
    @EnvironmentObject var audioService: AudioService
    @State private var selectedTab = 0
    
    var body: some View {
        NavigationView {
            TabView(selection: $selectedTab) {
                ConversationView()
                    .tabItem {
                        Image(systemName: "message.circle")
                        Text("Chat")
                    }
                    .tag(0)
                
                CRMView()
                    .tabItem {
                        Image(systemName: "person.3")
                        Text("CRM")
                    }
                    .tag(1)
                
                ERPView()
                    .tabItem {
                        Image(systemName: "box.truck")
                        Text("ERP")
                    }
                    .tag(2)
                
                DashboardView()
                    .tabItem {
                        Image(systemName: "chart.bar")
                        Text("Stats")
                    }
                    .tag(3)
            }
            .navigationTitle("WearForce")
        }
    }
}