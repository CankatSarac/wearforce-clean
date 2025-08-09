import SwiftUI

struct CRMView: View {
    @EnvironmentObject var apiService: APIService
    @State private var customers: [Customer] = []
    @State private var leads: [Lead] = []
    @State private var selectedSegment = 0
    @State private var isLoading = false
    
    var body: some View {
        VStack {
            // Segment Control
            Picker("CRM Section", selection: $selectedSegment) {
                Text("Customers").tag(0)
                Text("Leads").tag(1)
            }
            .pickerStyle(SegmentedPickerStyle())
            .padding(.horizontal)
            
            if isLoading {
                ProgressView("Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                switch selectedSegment {
                case 0:
                    CustomersListView(customers: customers)
                case 1:
                    LeadsListView(leads: leads)
                default:
                    EmptyView()
                }
            }
        }
        .navigationTitle("CRM")
        .onAppear {
            loadCRMData()
        }
        .onChange(of: selectedSegment) { _ in
            loadCRMData()
        }
    }
    
    private func loadCRMData() {
        isLoading = true
        
        Task {
            do {
                switch selectedSegment {
                case 0:
                    let fetchedCustomers = try await apiService.getCustomers()
                    await MainActor.run {
                        customers = fetchedCustomers
                        isLoading = false
                    }
                case 1:
                    let fetchedLeads = try await apiService.getLeads()
                    await MainActor.run {
                        leads = fetchedLeads
                        isLoading = false
                    }
                default:
                    break
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                }
                print("Error loading CRM data: \(error)")
            }
        }
    }
}

struct CustomersListView: View {
    let customers: [Customer]
    
    var body: some View {
        List(customers) { customer in
            NavigationLink(destination: CustomerDetailView(customer: customer)) {
                CustomerRowView(customer: customer)
            }
        }
        .listStyle(PlainListStyle())
    }
}

struct LeadsListView: View {
    let leads: [Lead]
    
    var body: some View {
        List(leads) { lead in
            NavigationLink(destination: LeadDetailView(lead: lead)) {
                LeadRowView(lead: lead)
            }
        }
        .listStyle(PlainListStyle())
    }
}

struct CustomerRowView: View {
    let customer: Customer
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(customer.name)
                .font(.headline)
                .lineLimit(1)
            
            Text(customer.company)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
            
            HStack {
                Image(systemName: "phone")
                    .font(.caption2)
                    .foregroundColor(.blue)
                Text(customer.phone)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                StatusBadge(status: customer.status)
            }
        }
        .padding(.vertical, 2)
    }
}

struct LeadRowView: View {
    let lead: Lead
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(lead.name)
                .font(.headline)
                .lineLimit(1)
            
            Text(lead.source)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
            
            HStack {
                Image(systemName: "dollarsign.circle")
                    .font(.caption2)
                    .foregroundColor(.green)
                Text("$\(lead.value, specifier: "%.0f")")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
                StatusBadge(status: lead.status)
            }
        }
        .padding(.vertical, 2)
    }
}

struct StatusBadge: View {
    let status: String
    
    private var statusColor: Color {
        switch status.lowercased() {
        case "active", "qualified":
            return .green
        case "pending", "new":
            return .orange
        case "inactive", "lost":
            return .red
        default:
            return .gray
        }
    }
    
    var body: some View {
        Text(status)
            .font(.caption2)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(statusColor.opacity(0.2))
            .foregroundColor(statusColor)
            .clipShape(Capsule())
    }
}

struct CustomerDetailView: View {
    let customer: Customer
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Customer Header
                VStack(alignment: .leading, spacing: 8) {
                    Text(customer.name)
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text(customer.company)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    StatusBadge(status: customer.status)
                }
                
                Divider()
                
                // Contact Information
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Contact")
                    
                    InfoRow(icon: "phone", text: customer.phone)
                    InfoRow(icon: "envelope", text: customer.email)
                    if let address = customer.address {
                        InfoRow(icon: "location", text: address)
                    }
                }
                
                Divider()
                
                // Quick Actions
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Actions")
                    
                    HStack(spacing: 12) {
                        ActionButton(icon: "phone.fill", title: "Call", color: .green) {
                            // Handle call action
                        }
                        
                        ActionButton(icon: "message.fill", title: "Message", color: .blue) {
                            // Handle message action
                        }
                        
                        ActionButton(icon: "plus", title: "Note", color: .orange) {
                            // Handle add note action
                        }
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Customer")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct LeadDetailView: View {
    let lead: Lead
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Lead Header
                VStack(alignment: .leading, spacing: 8) {
                    Text(lead.name)
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("$\(lead.value, specifier: "%.0f")")
                        .font(.title3)
                        .foregroundColor(.green)
                        .fontWeight(.semibold)
                    
                    StatusBadge(status: lead.status)
                }
                
                Divider()
                
                // Lead Information
                VStack(alignment: .leading, spacing: 8) {
                    SectionHeader(title: "Details")
                    
                    InfoRow(icon: "arrow.right.circle", text: "Source: \(lead.source)")
                    InfoRow(icon: "calendar", text: "Created: \(lead.createdAt.formatted(date: .abbreviated, time: .omitted))")
                    if let notes = lead.notes {
                        InfoRow(icon: "note.text", text: notes)
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Lead")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct SectionHeader: View {
    let title: String
    
    var body: some View {
        Text(title)
            .font(.headline)
            .fontWeight(.semibold)
    }
}

struct InfoRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(.blue)
                .frame(width: 16)
            
            Text(text)
                .font(.caption)
                .foregroundColor(.primary)
        }
    }
}

struct ActionButton: View {
    let icon: String
    let title: String
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundColor(.white)
                
                Text(title)
                    .font(.caption2)
                    .foregroundColor(.white)
            }
            .frame(width: 50, height: 50)
            .background(color)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(PlainButtonStyle())
    }
}