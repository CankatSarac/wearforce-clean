import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var apiService: APIService
    @State private var metrics: DashboardMetrics?
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationView {
            VStack {
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let errorMessage = errorMessage {
                    ErrorView(message: errorMessage) {
                        Task {
                            await loadDashboardData()
                        }
                    }
                } else if let metrics = metrics {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            // Key Metrics
                            MetricCard(
                                title: "Today's Sales",
                                value: metrics.todaysSales.currencyFormatted,
                                icon: "dollarsign.circle.fill",
                                color: .green
                            )
                            
                            MetricCard(
                                title: "Monthly Revenue",
                                value: metrics.monthlyRevenue.currencyFormatted,
                                icon: "chart.line.uptrend.xyaxis.circle.fill",
                                color: .blue
                            )
                            
                            MetricCard(
                                title: "Total Customers",
                                value: "\(metrics.totalCustomers)",
                                icon: "person.3.fill",
                                color: .orange
                            )
                            
                            MetricCard(
                                title: "Active Leads",
                                value: "\(metrics.activeLeads)",
                                icon: "target",
                                color: .purple
                            )
                            
                            MetricCard(
                                title: "Pending Orders",
                                value: "\(metrics.pendingOrders)",
                                icon: "box.truck.fill",
                                color: .red
                            )
                            
                            if metrics.lowStockItems > 0 {
                                MetricCard(
                                    title: "Low Stock Items",
                                    value: "\(metrics.lowStockItems)",
                                    icon: "exclamationmark.triangle.fill",
                                    color: .yellow
                                )
                            }
                        }
                        .padding(.horizontal, 8)
                    }
                } else {
                    EmptyStateView()
                }
            }
            .navigationTitle("Dashboard")
            .onAppear {
                Task {
                    await loadDashboardData()
                }
            }
            .refreshable {
                await loadDashboardData()
            }
        }
    }
    
    private func loadDashboardData() async {
        isLoading = true
        errorMessage = nil
        
        do {
            let dashboardMetrics = try await apiService.getDashboardMetrics()
            await MainActor.run {
                self.metrics = dashboardMetrics
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
            }
        }
        
        await MainActor.run {
            isLoading = false
        }
    }
}

struct MetricCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 4) {
            HStack {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(color)
                
                Spacer()
            }
            
            HStack {
                Text(value)
                    .font(.headline)
                    .fontWeight(.bold)
                    .foregroundColor(.primary)
                
                Spacer()
            }
            
            HStack {
                Text(title)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                
                Spacer()
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(color.opacity(0.1))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(color.opacity(0.2), lineWidth: 1)
        )
    }
}

struct ErrorView: View {
    let message: String
    let onRetry: () -> Void
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle")
                .font(.title2)
                .foregroundColor(.orange)
            
            Text(message)
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button(action: onRetry) {
                Text("Retry")
                    .font(.caption)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 4)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: "chart.bar.xaxis")
                .font(.title2)
                .foregroundColor(.gray)
            
            Text("No data available")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview {
    DashboardView()
        .environmentObject(APIService())
}