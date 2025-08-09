package wearforce-clean.data_access

import rego.v1

# Data access control policies specific to WearForce business logic

# Customer data access rules
allow_customer_access if {
    input.resource == "customer"
    input.method == "GET"
    customer_access_authorized
}

customer_access_authorized if {
    # Sales reps can only access their assigned customers
    input.user.role == "sales_rep"
    input.customer_id in input.user.assigned_customers
}

customer_access_authorized if {
    # Sales managers can access customers in their territory
    input.user.role == "sales_manager"
    input.customer.territory in input.user.territories
}

customer_access_authorized if {
    # Customer service can access customers with active tickets
    input.user.role == "customer_service"
    has_active_support_ticket
}

customer_access_authorized if {
    # Admins can access all customers
    input.user.role in ["crm_admin", "super_admin"]
}

has_active_support_ticket if {
    some ticket in input.support_tickets
    ticket.customer_id == input.customer_id
    ticket.status == "open"
    ticket.assigned_to == input.user.id
}

# Inventory access rules
allow_inventory_access if {
    input.resource == "inventory"
    inventory_access_authorized
}

inventory_access_authorized if {
    # Warehouse staff can only access inventory in their warehouse
    input.user.role == "warehouse_staff"
    input.inventory.warehouse_id in input.user.warehouses
}

inventory_access_authorized if {
    # Inventory managers can access all inventory data
    input.user.role in ["inventory_manager", "erp_admin", "super_admin"]
}

# Financial data access (PCI DSS compliance)
allow_financial_access if {
    input.resource_type == "financial"
    financial_access_authorized
    pci_compliance_met
}

financial_access_authorized if {
    input.user.role in ["super_admin", "finance_manager"]
    input.user.pci_certified == true
}

pci_compliance_met if {
    input.request.encrypted == true
    input.session.secure == true
    time_within_business_hours
}

time_within_business_hours if {
    hour := time.now_ns() / 1000000000 / 3600 % 24
    hour >= 8
    hour <= 18
}

# Export restrictions
allow_data_export if {
    export_authorized
    export_compliance_met
}

export_authorized if {
    input.user.role in ["super_admin", "data_protection_officer"]
    input.export_request.approved == true
}

export_compliance_met if {
    # GDPR compliance for EU data
    input.data.region == "EU"
    input.export_request.gdpr_basis != ""
    input.export_request.data_subject_consent == true
}

export_compliance_met if {
    # Non-EU data
    input.data.region != "EU"
}

# Data retention compliance
allow_data_retention if {
    within_retention_period
    proper_data_classification
}

within_retention_period if {
    data_age_days := (time.now_ns() - input.data.created_at) / (24 * 3600 * 1000000000)
    retention_days := data_retention_period[input.data.classification]
    data_age_days <= retention_days
}

data_retention_period := {
    "public": 365,
    "internal": 1095,    # 3 years
    "confidential": 2555, # 7 years
    "pii": 2555,         # 7 years
    "payment": 2555      # 7 years (financial records)
}

proper_data_classification if {
    input.data.classification in ["public", "internal", "confidential", "pii", "payment"]
}

# Cross-service data sharing
allow_cross_service_access if {
    service_authorized
    data_sharing_agreement_exists
}

service_authorized if {
    input.source_service in authorized_services[input.target_service]
}

authorized_services := {
    "crm": ["notification", "graphql-gateway"],
    "erp": ["notification", "graphql-gateway", "crm"],
    "notification": ["crm", "erp", "graphql-gateway"],
    "graphql-gateway": ["crm", "erp", "notification"]
}

data_sharing_agreement_exists if {
    input.data_sharing_agreement.exists == true
    input.data_sharing_agreement.expires_at > time.now_ns()
}

# Multi-tenant data isolation
allow_tenant_access if {
    tenant_data_isolated
    user_tenant_authorized
}

tenant_data_isolated if {
    input.data.tenant_id == input.request.tenant_id
}

user_tenant_authorized if {
    input.user.tenant_id == input.request.tenant_id
}

# Sensitive data masking rules
apply_data_masking if {
    contains_sensitive_data
    not full_access_authorized
}

contains_sensitive_data if {
    input.data.classification in ["pii", "payment", "confidential"]
}

full_access_authorized if {
    input.user.role in ["super_admin", "data_protection_officer"]
    input.user.full_access_approved == true
}

# Audit requirements for data access
audit_required if {
    high_risk_data_access
}

audit_required if {
    administrative_action
}

high_risk_data_access if {
    input.data.classification in ["payment", "pii"]
}

high_risk_data_access if {
    input.method in ["DELETE", "PUT"]
    input.data.classification in ["confidential", "pii", "payment"]
}

administrative_action if {
    input.user.role in ["super_admin", "crm_admin", "erp_admin"]
    input.method in ["POST", "PUT", "DELETE"]
}

# Data quality and validation rules
data_quality_check_required if {
    input.method in ["POST", "PUT"]
    input.data.classification in ["confidential", "pii", "payment"]
}

# Response with detailed access control information
access_decision := {
    "allow": allow_access,
    "customer_access": allow_customer_access,
    "inventory_access": allow_inventory_access,
    "financial_access": allow_financial_access,
    "export_allowed": allow_data_export,
    "retention_compliant": allow_data_retention,
    "cross_service_allowed": allow_cross_service_access,
    "tenant_access_allowed": allow_tenant_access,
    "masking_required": apply_data_masking,
    "audit_required": audit_required,
    "data_quality_check_required": data_quality_check_required,
    "timestamp": time.now_ns(),
    "evaluated_by": "wearforce-clean.data_access"
}

allow_access if {
    allow_customer_access
}

allow_access if {
    allow_inventory_access  
}

allow_access if {
    allow_financial_access
}

allow_access if {
    allow_data_export
}

allow_access if {
    allow_cross_service_access
}

allow_access if {
    allow_tenant_access
}