package wearforce.authz

import rego.v1

# Default deny
default allow := false

# Allow if user has valid JWT and required permissions
allow if {
    input.method == "GET"
    token_valid
    has_permission("read")
}

allow if {
    input.method == "POST"
    token_valid
    has_permission("write")
}

allow if {
    input.method == "PUT"
    token_valid
    has_permission("write")
}

allow if {
    input.method == "DELETE"
    token_valid
    has_permission("delete")
}

# Admin access
allow if {
    token_valid
    has_role("super_admin")
}

allow if {
    token_valid
    has_role("admin")
    admin_endpoints
}

# Public endpoints (no auth required)
allow if {
    public_endpoints
}

# Health check endpoints
allow if {
    input.path == ["/health"]
}

allow if {
    input.path == ["/metrics"]
}

allow if {
    input.path == ["/ping"]
}

# Service-to-service authentication
allow if {
    service_auth
}

# Device-specific access
allow if {
    token_valid
    device_access
}

# Token validation
token_valid if {
    token := bearer_token
    token != ""
    jwt_valid(token)
}

# Extract bearer token
bearer_token := token if {
    auth_header := input.headers.authorization
    startswith(auth_header, "Bearer ")
    token := substring(auth_header, 7, -1)
}

# JWT validation (simplified - in production, verify with Keycloak)
jwt_valid(token) if {
    [header, payload, signature] := io.jwt.decode(token)
    payload.exp > time.now_ns() / 1000000000
    payload.iss == "http://keycloak:8080/auth/realms/wearforce"
}

# Role checks
has_role(required_role) if {
    token := bearer_token
    [_, payload, _] := io.jwt.decode(token)
    required_role in payload.realm_access.roles
}

has_role(required_role) if {
    token := bearer_token
    [_, payload, _] := io.jwt.decode(token)
    client_roles := payload.resource_access[_].roles
    required_role in client_roles
}

# Permission checks based on roles and endpoints
has_permission(action) if {
    has_role("super_admin")
}

has_permission("read") if {
    some role in ["user", "sales_rep", "customer_service", "warehouse_staff"]
    has_role(role)
}

has_permission("write") if {
    some role in ["sales_manager", "inventory_manager", "crm_admin", "erp_admin"]
    has_role(role)
}

has_permission("delete") if {
    some role in ["admin", "crm_admin", "erp_admin"]
    has_role(role)
}

# Public endpoints
public_endpoints if {
    input.path == ["/docs"]
}

public_endpoints if {
    startswith(concat("/", input.path), "/swagger")
}

public_endpoints if {
    input.path == ["/favicon.ico"]
}

# Admin endpoints
admin_endpoints if {
    startswith(concat("/", input.path), "/admin")
}

admin_endpoints if {
    startswith(concat("/", input.path), "/api/admin")
}

# Service authentication
service_auth if {
    input.headers["x-service-token"]
    # Validate service token
}

# Device-specific access patterns
device_access if {
    token := bearer_token
    [_, payload, _] := io.jwt.decode(token)
    payload.device_type in ["watch", "wearable"]
    device_endpoints
}

device_endpoints if {
    startswith(concat("/", input.path), "/api/device")
}

device_endpoints if {
    input.path == ["/api", "audio", "stream"]
}

device_endpoints if {
    input.path == ["/ws"]
}

# CRM specific access control
crm_access if {
    startswith(concat("/", input.path), "/api/crm")
    some role in ["crm_admin", "sales_manager", "sales_rep"]
    has_role(role)
}

# ERP specific access control  
erp_access if {
    startswith(concat("/", input.path), "/api/erp")
    some role in ["erp_admin", "inventory_manager", "warehouse_staff"]
    has_role(role)
}

# Time-based access control
working_hours if {
    now := time.now_ns()
    hour := time.clock(now)[0]
    hour >= 6
    hour <= 22
}

# Rate limiting decision
rate_limit_exceeded if {
    user_id := get_user_id
    current_requests := get_user_requests(user_id)
    current_requests > 100  # requests per minute
}

get_user_id := user_id if {
    token := bearer_token
    [_, payload, _] := io.jwt.decode(token)
    user_id := payload.sub
}

get_user_requests(user_id) := count if {
    # This would integrate with Redis to get actual request count
    count := 0
}

# Data classification and access
sensitive_data_access if {
    contains(concat("/", input.path), "/pii")
    has_role("admin")
}

pci_data_access if {
    contains(concat("/", input.path), "/payment")
    has_role("admin")
    # Additional PCI compliance checks would go here
}

# Geo-fencing (example for compliance)
geo_allowed if {
    client_country := input.headers["cf-ipcountry"]  # Cloudflare header
    client_country in ["US", "CA", "GB", "DE", "FR"]  # Allowed countries
}

# Audit logging decisions
audit_required if {
    sensitive_endpoints
}

audit_required if {
    admin_endpoints
}

audit_required if {
    input.method in ["POST", "PUT", "DELETE"]
}

sensitive_endpoints if {
    contains(concat("/", input.path), "/admin")
}

sensitive_endpoints if {
    contains(concat("/", input.path), "/pii")
}

sensitive_endpoints if {
    contains(concat("/", input.path), "/payment")
}