import SwiftUI

struct ERPView: View {
    @EnvironmentObject var apiService: APIService
    @State private var orders: [Order] = []
    @State private var inventory: [InventoryItem] = []
    @State private var selectedSegment = 0
    @State private var isLoading = false
    
    var body: some View {
        VStack {
            // Segment Control
            Picker("ERP Section", selection: $selectedSegment) {
                Text("Orders").tag(0)
                Text("Inventory").tag(1)
            }
            .pickerStyle(SegmentedPickerStyle())
            .padding(.horizontal)
            
            if isLoading {
                ProgressView("Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                switch selectedSegment {
                case 0:
                    OrdersListView(orders: orders)
                case 1:
                    InventoryListView(inventory: inventory)
                default:
                    EmptyView()
                }
            }
        }
        .navigationTitle("ERP")
        .onAppear {
            loadERPData()
        }
        .onChange(of: selectedSegment) { _ in
            loadERPData()
        }
    }
    
    private func loadERPData() {
        isLoading = true
        
        Task {
            do {
                switch selectedSegment {
                case 0:
                    let fetchedOrders = try await apiService.getOrders()
                    await MainActor.run {
                        orders = fetchedOrders
                        isLoading = false
                    }
                case 1:
                    let fetchedInventory = try await apiService.getInventory()
                    await MainActor.run {
                        inventory = fetchedInventory
                        isLoading = false
                    }
                default:
                    break
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                }
                print("Error loading ERP data: \(error)")
            }
        }
    }
}

struct OrdersListView: View {
    let orders: [Order]
    
    var body: some View {
        List(orders) { order in
            NavigationLink(destination: OrderDetailView(order: order)) {
                OrderRowView(order: order)
            }
        }
        .listStyle(PlainListStyle())
    }
}

struct InventoryListView: View {
    let inventory: [InventoryItem]
    
    var body: some View {
        List(inventory) { item in
            NavigationLink(destination: InventoryDetailView(item: item)) {
                InventoryRowView(item: item)
            }
        }
        .listStyle(PlainListStyle())
    }
}

struct OrderRowView: View {
    let order: Order
    
    private var statusColor: Color {
        switch order.status.lowercased() {
        case "pending":
            return .orange
        case "processing":
            return .blue
        case "shipped":
            return .green
        case "delivered":
            return .green
        case "cancelled":
            return .red
        default:
            return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Order #\(order.orderNumber)")
                    .font(.headline)
                    .lineLimit(1)
                Spacer()
                StatusBadge(status: order.status, color: statusColor)
            }
            
            Text(order.customerName)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
            
            HStack {
                Image(systemName: "dollarsign.circle")
                    .font(.caption2)
                    .foregroundColor(.green)
                Text("$\(order.total, specifier: "%.2f")")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                Text(order.createdAt.formatted(date: .abbreviated, time: .omitted))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct InventoryRowView: View {
    let item: InventoryItem
    
    private var stockColor: Color {
        if item.quantity <= item.lowStockThreshold {
            return .red
        } else if item.quantity <= item.lowStockThreshold * 2 {
            return .orange
        } else {
            return .green
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(item.name)
                .font(.headline)
                .lineLimit(1)
            
            Text(item.sku)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
            
            HStack {
                Image(systemName: "cube")
                    .font(.caption2)
                    .foregroundColor(stockColor)
                Text("\(item.quantity) in stock")
                    .font(.caption2)
                    .foregroundColor(stockColor)
                Spacer()
                Text("$\(item.price, specifier: "%.2f")")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct OrderDetailView: View {
    let order: Order
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Order Header
                VStack(alignment: .leading, spacing: 8) {
                    Text("Order #\(order.orderNumber)")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("$\(order.total, specifier: "%.2f")")
                        .font(.title3)
                        .foregroundColor(.green)
                        .fontWeight(.semibold)
                    
                    StatusBadge(status: order.status, color: .blue)
                }
                
                Divider()
                
                // Customer Information
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Customer")
                    
                    InfoRow(icon: "person", text: order.customerName)
                    if let email = order.customerEmail {
                        InfoRow(icon: "envelope", text: email)
                    }
                    if let address = order.shippingAddress {
                        InfoRow(icon: "location", text: address)
                    }
                }
                
                Divider()
                
                // Order Items
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Items")
                    
                    ForEach(order.items, id: \.id) { item in
                        OrderItemRow(item: item)
                    }
                }
                
                Divider()
                
                // Order Timeline
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Timeline")
                    
                    InfoRow(icon: "calendar", text: "Created: \(order.createdAt.formatted())")
                    if let updatedAt = order.updatedAt {
                        InfoRow(icon: "clock", text: "Updated: \(updatedAt.formatted())")
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Order")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct InventoryDetailView: View {
    let item: InventoryItem
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Item Header
                VStack(alignment: .leading, spacing: 8) {
                    Text(item.name)
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("$\(item.price, specifier: "%.2f")")
                        .font(.title3)
                        .foregroundColor(.green)
                        .fontWeight(.semibold)
                }
                
                Divider()
                
                // Item Information
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Details")
                    
                    InfoRow(icon: "number", text: "SKU: \(item.sku)")
                    InfoRow(icon: "cube", text: "Quantity: \(item.quantity)")
                    InfoRow(icon: "exclamationmark.triangle", text: "Low Stock: \(item.lowStockThreshold)")
                    if let category = item.category {
                        InfoRow(icon: "tag", text: "Category: \(category)")
                    }
                }
                
                Divider()
                
                // Stock Status
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Stock Status")
                    
                    HStack {
                        Text("Current Stock")
                            .font(.caption)
                        Spacer()
                        Text("\(item.quantity)")
                            .font(.caption)
                            .fontWeight(.semibold)
                    }
                    
                    ProgressView(value: Double(item.quantity), total: Double(max(item.quantity, item.lowStockThreshold * 3)))
                        .progressViewStyle(LinearProgressViewStyle(tint: stockColor))
                }
            }
            .padding()
        }
        .navigationTitle("Inventory")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    private var stockColor: Color {
        if item.quantity <= item.lowStockThreshold {
            return .red
        } else if item.quantity <= item.lowStockThreshold * 2 {
            return .orange
        } else {
            return .green
        }
    }
}

struct OrderItemRow: View {
    let item: OrderItem
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(item.name)
                    .font(.caption)
                    .fontWeight(.medium)
                Text("Qty: \(item.quantity)")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("$\(item.price * Double(item.quantity), specifier: "%.2f")")
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.vertical, 2)
    }
}

extension StatusBadge {
    init(status: String, color: Color) {
        self.init(status: status)
    }
}

struct DashboardView: View {
    @EnvironmentObject var apiService: APIService
    @State private var metrics: DashboardMetrics?
    @State private var isLoading = false
    
    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let metrics = metrics {
                VStack(spacing: 16) {
                    // Key Metrics
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 12) {
                        MetricCard(title: "Today's Sales", value: "$\(metrics.todaysSales, specifier: "%.0f")", color: .green)
                        MetricCard(title: "Open Leads", value: "\(metrics.openLeads)", color: .blue)
                        MetricCard(title: "Pending Orders", value: "\(metrics.pendingOrders)", color: .orange)
                        MetricCard(title: "Low Stock Items", value: "\(metrics.lowStockItems)", color: .red)
                    }
                    
                    // Recent Activity
                    VStack(alignment: .leading, spacing: 8) {
                        SectionHeader(title: "Recent Activity")
                        
                        ForEach(metrics.recentActivities.prefix(3), id: \.id) { activity in
                            ActivityRow(activity: activity)
                        }
                    }
                }
                .padding()
            } else {
                Text("No data available")
                    .foregroundColor(.secondary)
            }
        }
        .navigationTitle("Dashboard")
        .onAppear {
            loadDashboardData()
        }
        .refreshable {
            loadDashboardData()
        }
    }
    
    private func loadDashboardData() {
        isLoading = true
        
        Task {
            do {
                let fetchedMetrics = try await apiService.getDashboardMetrics()
                await MainActor.run {
                    metrics = fetchedMetrics
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                }
                print("Error loading dashboard data: \(error)")
            }
        }
    }
}

struct MetricCard: View {
    let title: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(color)
            
            Text(title)
                .font(.caption2)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct ActivityRow: View {
    let activity: RecentActivity
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: activity.icon)
                .font(.caption)
                .foregroundColor(.blue)
                .frame(width: 16)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(activity.title)
                    .font(.caption)
                    .fontWeight(.medium)
                    .lineLimit(1)
                
                Text(activity.timestamp.formatted(date: .omitted, time: .shortened))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
    }
}