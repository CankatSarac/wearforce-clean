package wearforce-clean.authz

import rego.v1

# Default deny all requests
default allow := false

# Default RBAC permissions
default has_permission := false

# WearForce Business Rules and Authorization Policies
# This policy implements role-based access control (RBAC) with business-specific rules

# User roles hierarchy (higher roles inherit lower role permissions)
role_hierarchy := {
    "super_admin": ["super_admin", "crm_admin", "erp_admin", "sales_manager", "inventory_manager", "customer_service", "user"],
    "crm_admin": ["crm_admin", "sales_manager", "customer_service", "user"],
    "erp_admin": ["erp_admin", "inventory_manager", "warehouse_staff", "user"],
    "sales_manager": ["sales_manager", "sales_rep", "customer_service", "user"],
    "inventory_manager": ["inventory_manager", "warehouse_staff", "user"],
    "sales_rep": ["sales_rep", "user"],
    "warehouse_staff": ["warehouse_staff", "user"],
    "customer_service": ["customer_service", "user"],
    "user": ["user"]
}

# Service endpoints and their required permissions
service_permissions := {
    # CRM Service Permissions
    "GET /crm/customers": ["crm:read"],
    "POST /crm/customers": ["crm:write"],
    "PUT /crm/customers/*": ["crm:write"],
    "DELETE /crm/customers/*": ["crm:delete"],
    "GET /crm/leads": ["crm:read"],
    "POST /crm/leads": ["crm:write"],
    "PUT /crm/leads/*": ["crm:write"],
    "DELETE /crm/leads/*": ["crm:delete"],
    "GET /crm/contacts": ["crm:read"],
    "POST /crm/contacts": ["crm:write"],
    "PUT /crm/contacts/*": ["crm:write"],
    "DELETE /crm/contacts/*": ["crm:delete"],
    "GET /crm/opportunities": ["crm:read"],
    "POST /crm/opportunities": ["crm:write"],
    "PUT /crm/opportunities/*": ["crm:write"],
    "DELETE /crm/opportunities/*": ["crm:delete"],
    
    # ERP Service Permissions
    "GET /erp/inventory": ["erp:read"],
    "POST /erp/inventory": ["erp:write"],
    "PUT /erp/inventory/*": ["erp:write"],
    "DELETE /erp/inventory/*": ["erp:delete"],
    "GET /erp/suppliers": ["erp:read"],
    "POST /erp/suppliers": ["erp:write"],
    "PUT /erp/suppliers/*": ["erp:write"],
    "DELETE /erp/suppliers/*": ["erp:delete"],
    "GET /erp/orders": ["erp:read"],
    "POST /erp/orders": ["erp:write"],
    "PUT /erp/orders/*": ["erp:write"],
    "DELETE /erp/orders/*": ["erp:delete"],
    "GET /erp/products": ["erp:read"],
    "POST /erp/products": ["erp:write"],
    "PUT /erp/products/*": ["erp:write"],
    "DELETE /erp/products/*": ["erp:delete"],
    
    # Notification Service Permissions
    "GET /notifications": ["notification:read"],
    "POST /notifications": ["notification:send"],
    "PUT /notifications/*": ["notification:write"],
    "DELETE /notifications/*": ["notification:admin"],
    
    # Admin endpoints
    "GET /admin/*": ["system:admin"],
    "POST /admin/*": ["system:admin"],
    "PUT /admin/*": ["system:admin"],
    "DELETE /admin/*": ["system:admin"],
    
    # Health and monitoring endpoints (public)
    "GET /health": [],
    "GET /metrics": [],
    "GET /ready": []
}

# Role-based permissions mapping
role_permissions := {
    "super_admin": [
        "system:admin", "crm:admin", "erp:admin", "notification:admin",
        "crm:read", "crm:write", "crm:delete", 
        "erp:read", "erp:write", "erp:delete",
        "notification:read", "notification:send", "notification:write"
    ],
    "crm_admin": [
        "crm:admin", "crm:read", "crm:write", "crm:delete",
        "notification:read", "notification:send"
    ],
    "erp_admin": [
        "erp:admin", "erp:read", "erp:write", "erp:delete",
        "notification:read", "notification:send"
    ],
    "sales_manager": [
        "crm:read", "crm:write", 
        "erp:read",
        "notification:read", "notification:send"
    ],
    "sales_rep": [
        "crm:read", "crm:write",
        "notification:read"
    ],
    "inventory_manager": [
        "erp:read", "erp:write",
        "notification:read", "notification:send"
    ],
    "warehouse_staff": [
        "erp:read",
        "notification:read"
    ],
    "customer_service": [
        "crm:read", "crm:write",
        "notification:read", "notification:send"
    ],
    "user": [
        "notification:read"
    ]
}

# Business rules for data access
# Sales representatives can only access their own customer data
allow if {
    input.method == "GET"
    contains(input.path, "/crm/customers")
    user_has_role("sales_rep")
    not user_has_role("sales_manager")
    customer_belongs_to_user
}

# Inventory staff can only modify inventory for their assigned warehouse
allow if {
    input.method in ["PUT", "POST"]
    contains(input.path, "/erp/inventory")
    user_has_role("warehouse_staff")
    inventory_in_assigned_warehouse
}

# Financial data access restrictions (PCI DSS compliance)
allow if {
    contains(input.path, "/erp/orders")
    contains(input.path, "/payment")
    user_has_permission("erp:admin")
    time_within_business_hours
    request_from_secure_location
}

# Time-based access controls
allow if {
    input.method == "DELETE"
    contains(input.path, "/crm/")
    user_has_permission("crm:delete")
    time_within_business_hours
    requires_approval_for_deletion
}

# Main authorization logic
allow if {
    # Public endpoints
    endpoint_requires_no_auth
}

allow if {
    # Authenticated endpoints with proper permissions
    user_authenticated
    user_has_required_permissions
    not violates_business_rules
    within_rate_limits
    passes_security_checks
}

# Helper functions
user_authenticated if {
    input.user
    input.user.id
    input.user.email
    input.user.roles
}

user_has_role(role) if {
    role in input.user.roles
}

user_has_permission(permission) if {
    some role in input.user.roles
    permission in role_permissions[role]
}

user_has_required_permissions if {
    endpoint_key := sprintf("%s %s", [input.method, input.path])
    required_perms := service_permissions[endpoint_key]
    count(required_perms) == 0
}

user_has_required_permissions if {
    endpoint_key := sprintf("%s %s", [input.method, input.path])
    required_perms := service_permissions[endpoint_key]
    count(required_perms) > 0
    some perm in required_perms
    user_has_permission(perm)
}

endpoint_requires_no_auth if {
    endpoint_key := sprintf("%s %s", [input.method, input.path])
    required_perms := service_permissions[endpoint_key]
    count(required_perms) == 0
}

# Business rule implementations
customer_belongs_to_user if {
    # Extract customer ID from path
    path_parts := split(input.path, "/")
    customer_id := path_parts[count(path_parts) - 1]
    
    # Check if customer is assigned to this sales rep
    customer_id in input.user.assigned_customers
}

inventory_in_assigned_warehouse if {
    # Extract inventory location from request body or path
    input.body.warehouse_id in input.user.assigned_warehouses
}

time_within_business_hours if {
    # Get current time (would be injected by the policy engine)
    current_hour := time.now_ns() / 1000000000 / 3600 % 24
    current_hour >= 8  # 8 AM
    current_hour <= 18 # 6 PM
}

request_from_secure_location if {
    # Check if request comes from approved IP ranges
    some allowed_ip in input.security.allowed_ip_ranges
    net.cidr_contains(allowed_ip, input.remote_addr)
}

requires_approval_for_deletion if {
    # Deletion of critical records requires approval
    contains(input.path, "/customers/")
    input.user.approval_token
    input.user.approval_token != ""
}

violates_business_rules if {
    # Check various business rule violations
    violates_data_sovereignty
}

violates_business_rules if {
    violates_gdpr_consent
}

violates_business_rules if {
    violates_pci_requirements
}

violates_data_sovereignty if {
    # EU users' data must be processed in EU regions
    input.user.region == "EU"
    not input.processing_region == "EU"
}

violates_gdpr_consent if {
    # Check GDPR consent for data processing
    requires_gdpr_consent
    not has_valid_gdpr_consent
}

violates_pci_requirements if {
    # PCI DSS requirements for payment data
    accesses_payment_data
    not user_has_permission("payment:access")
}

requires_gdpr_consent if {
    # Marketing and analytics operations require consent
    input.operation_type in ["marketing", "analytics", "profiling"]
    input.user.region in ["EU", "UK"]
}

has_valid_gdpr_consent if {
    input.user.gdpr_consent
    input.user.gdpr_consent.status == "granted"
    time.now_ns() < input.user.gdpr_consent.expires_at
}

accesses_payment_data if {
    # Payment-related endpoints
    contains(input.path, "/payment")
}

accesses_payment_data if {
    # Order endpoints with payment information
    contains(input.path, "/orders")
    contains(input.query.fields, "payment")
}

within_rate_limits if {
    # Rate limiting check (would be implemented by external system)
    input.rate_limit.current_requests < input.rate_limit.max_requests
}

passes_security_checks if {
    # Security validation
    not suspicious_activity_detected
    valid_user_agent
    not blacklisted_ip
}

suspicious_activity_detected if {
    # Multiple failed authentication attempts
    input.security.failed_attempts > 5
}

suspicious_activity_detected if {
    # Unusual access patterns
    input.security.unusual_activity == true
}

valid_user_agent if {
    # Block requests with no user agent or suspicious user agents
    input.headers["user-agent"]
    not contains(lower(input.headers["user-agent"]), "bot")
    not contains(lower(input.headers["user-agent"]), "crawler")
    not contains(lower(input.headers["user-agent"]), "scanner")
}

blacklisted_ip if {
    # Check against IP blacklist
    input.remote_addr in input.security.blacklisted_ips
}

# Additional security policies

# Data export restrictions
allow if {
    input.method == "GET"
    contains(input.path, "/export")
    user_has_permission("system:admin")
    data_export_approved
    encryption_required
}

data_export_approved if {
    input.export_request.approved_by
    input.export_request.approval_date
    time.now_ns() - input.export_request.approval_date < (7 * 24 * 3600 * 1000000000) # 7 days
}

encryption_required if {
    input.export_request.encryption_enabled == true
    input.export_request.encryption_key_id
}

# Multi-tenant isolation
allow if {
    input.tenant_id
    user_belongs_to_tenant
    data_belongs_to_tenant
}

user_belongs_to_tenant if {
    input.user.tenant_id == input.tenant_id
}

data_belongs_to_tenant if {
    # Ensure data being accessed belongs to user's tenant
    input.resource_tenant_id == input.tenant_id
}

# Audit logging requirements
audit_required if {
    # All admin actions require auditing
    user_has_role("super_admin")
}

audit_required if {
    # Financial data access requires auditing
    accesses_payment_data
}

audit_required if {
    # PII data access requires auditing
    accesses_pii_data
}

accesses_pii_data if {
    contains(input.path, "/customers")
    input.method in ["GET", "PUT", "DELETE"]
}

# Compliance rules
compliance_violation if {
    # GDPR violations
    violates_gdpr_consent
}

compliance_violation if {
    # PCI DSS violations
    violates_pci_requirements
}

compliance_violation if {
    # SOX compliance for financial data
    violates_sox_requirements
}

violates_sox_requirements if {
    # Financial reporting data requires additional controls
    contains(input.path, "/financial-reports")
    not user_has_role("super_admin")
    not financial_approval_workflow_completed
}

financial_approval_workflow_completed if {
    input.approval_workflow
    input.approval_workflow.status == "approved"
    input.approval_workflow.approver_role in ["cfo", "finance_manager"]
}

# Error responses with detailed information
deny_reason := reason if {
    not allow
    not user_authenticated
    reason := "Authentication required"
}

deny_reason := reason if {
    not allow
    user_authenticated
    not user_has_required_permissions
    reason := "Insufficient permissions"
}

deny_reason := reason if {
    not allow
    violates_business_rules
    reason := "Request violates business rules"
}

deny_reason := reason if {
    not allow
    compliance_violation
    reason := "Request violates compliance requirements"
}

deny_reason := reason if {
    not allow
    not within_rate_limits
    reason := "Rate limit exceeded"
}

deny_reason := reason if {
    not allow
    not passes_security_checks
    reason := "Security validation failed"
}

# Response structure
response := {
    "allow": allow,
    "reason": deny_reason,
    "audit_required": audit_required,
    "compliance_violation": compliance_violation,
    "user_permissions": [perm | some role in input.user.roles; perm in role_permissions[role]],
    "required_permissions": service_permissions[sprintf("%s %s", [input.method, input.path])],
    "timestamp": time.now_ns(),
    "request_id": input.request_id
}