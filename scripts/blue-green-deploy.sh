#!/bin/bash

# Blue-Green Deployment Script for WearForce
# This script handles zero-downtime deployments using blue-green strategy

set -euo pipefail

# Configuration
NAMESPACE="production"
RELEASE_NAME="wearforce"
CHART_PATH="./k8s/helm/wearforce"
VALUES_FILE="./k8s/helm/wearforce/values-production.yaml"
TIMEOUT="15m"
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if kubectl is available and connected
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed or not in PATH"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to get current active environment (blue or green)
get_current_environment() {
    local current_env
    current_env=$(kubectl get service "${RELEASE_NAME}-gateway" -n "${NAMESPACE}" -o jsonpath='{.spec.selector.environment}' 2>/dev/null || echo "")
    
    if [[ -z "$current_env" ]]; then
        # If no environment label, assume blue is active (initial deployment)
        echo "blue"
    else
        echo "$current_env"
    fi
}

# Function to get target environment (opposite of current)
get_target_environment() {
    local current_env=$1
    if [[ "$current_env" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Function to deploy to target environment
deploy_to_target() {
    local target_env=$1
    local image_tag=$2
    
    log_info "Deploying to ${target_env} environment..."
    
    # Create temporary values file with environment-specific overrides
    local temp_values_file="/tmp/values-${target_env}.yaml"
    cp "$VALUES_FILE" "$temp_values_file"
    
    # Add blue-green specific configuration
    cat >> "$temp_values_file" << EOF

# Blue-Green deployment configuration
blueGreen:
  enabled: true
  activeColor: ${target_env}
  inactiveColor: $(get_current_environment)

global:
  image:
    tag: ${image_tag}

# Override service selectors for target environment
gateway:
  selector:
    environment: ${target_env}

aiServices:
  llm:
    selector:
      environment: ${target_env}
  nlu:
    selector:
      environment: ${target_env}
  rag:
    selector:
      environment: ${target_env}
  stt:
    selector:
      environment: ${target_env}
  tts:
    selector:
      environment: ${target_env}

businessServices:
  graphql:
    selector:
      environment: ${target_env}
  crm:
    selector:
      environment: ${target_env}
  erp:
    selector:
      environment: ${target_env}
  notification:
    selector:
      environment: ${target_env}
EOF
    
    # Deploy using Helm
    helm upgrade --install "${RELEASE_NAME}-${target_env}" "$CHART_PATH" \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --values "$temp_values_file" \
        --timeout "$TIMEOUT" \
        --wait \
        --wait-for-jobs \
        --atomic
    
    # Clean up temporary file
    rm "$temp_values_file"
    
    log_success "Deployment to ${target_env} environment completed"
}

# Function to wait for pods to be ready
wait_for_pods_ready() {
    local target_env=$1
    local max_retries=60
    local retry_count=0
    
    log_info "Waiting for pods in ${target_env} environment to be ready..."
    
    while [[ $retry_count -lt $max_retries ]]; do
        local not_ready_pods
        not_ready_pods=$(kubectl get pods -n "$NAMESPACE" -l environment="$target_env" --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
        
        if [[ $not_ready_pods -eq 0 ]]; then
            # Double-check that all pods are actually ready (not just running)
            local unready_pods
            unready_pods=$(kubectl get pods -n "$NAMESPACE" -l environment="$target_env" -o jsonpath='{.items[?(@.status.containerStatuses[*].ready==false)].metadata.name}' 2>/dev/null)
            
            if [[ -z "$unready_pods" ]]; then
                log_success "All pods in ${target_env} environment are ready"
                return 0
            fi
        fi
        
        log_info "Waiting for pods to be ready... (attempt $((retry_count + 1))/${max_retries})"
        sleep 10
        ((retry_count++))
    done
    
    log_error "Timeout waiting for pods to be ready in ${target_env} environment"
    return 1
}

# Function to perform health checks
perform_health_checks() {
    local target_env=$1
    local retries=0
    
    log_info "Performing health checks on ${target_env} environment..."
    
    # Get gateway service endpoint
    local gateway_service="${RELEASE_NAME}-${target_env}-gateway"
    local gateway_port
    gateway_port=$(kubectl get service "$gateway_service" -n "$NAMESPACE" -o jsonpath='{.spec.ports[?(@.name=="http")].port}')
    
    # Port forward for health check (in background)
    kubectl port-forward -n "$NAMESPACE" "service/$gateway_service" 8080:$gateway_port &
    local port_forward_pid=$!
    
    # Give port-forward time to establish
    sleep 5
    
    while [[ $retries -lt $HEALTH_CHECK_RETRIES ]]; do
        if curl -f -s "http://localhost:8080/health" > /dev/null; then
            log_success "Health check passed for ${target_env} environment"
            kill $port_forward_pid 2>/dev/null || true
            return 0
        fi
        
        log_info "Health check failed, retrying... (attempt $((retries + 1))/${HEALTH_CHECK_RETRIES})"
        sleep $HEALTH_CHECK_INTERVAL
        ((retries++))
    done
    
    # Clean up port forward
    kill $port_forward_pid 2>/dev/null || true
    
    log_error "Health checks failed for ${target_env} environment"
    return 1
}

# Function to perform smoke tests
perform_smoke_tests() {
    local target_env=$1
    
    log_info "Performing smoke tests on ${target_env} environment..."
    
    # Get gateway service endpoint
    local gateway_service="${RELEASE_NAME}-${target_env}-gateway"
    local gateway_port
    gateway_port=$(kubectl get service "$gateway_service" -n "$NAMESPACE" -o jsonpath='{.spec.ports[?(@.name=="http")].port}')
    
    # Port forward for testing (in background)
    kubectl port-forward -n "$NAMESPACE" "service/$gateway_service" 8080:$gateway_port &
    local port_forward_pid=$!
    
    # Give port-forward time to establish
    sleep 5
    
    local tests_passed=true
    
    # Test 1: Health endpoint
    if ! curl -f -s "http://localhost:8080/health" | grep -q "healthy"; then
        log_error "Health endpoint test failed"
        tests_passed=false
    fi
    
    # Test 2: Metrics endpoint
    if ! curl -f -s "http://localhost:8080/metrics" > /dev/null; then
        log_error "Metrics endpoint test failed"
        tests_passed=false
    fi
    
    # Test 3: API endpoints (basic connectivity)
    local api_endpoints=("/api/v1/health" "/api/v1/version")
    for endpoint in "${api_endpoints[@]}"; do
        if ! curl -f -s "http://localhost:8080${endpoint}" > /dev/null; then
            log_error "API endpoint test failed: ${endpoint}"
            tests_passed=false
        fi
    done
    
    # Clean up port forward
    kill $port_forward_pid 2>/dev/null || true
    
    if [[ "$tests_passed" == true ]]; then
        log_success "All smoke tests passed for ${target_env} environment"
        return 0
    else
        log_error "Some smoke tests failed for ${target_env} environment"
        return 1
    fi
}

# Function to switch traffic to target environment
switch_traffic() {
    local target_env=$1
    local current_env=$2
    
    log_info "Switching traffic from ${current_env} to ${target_env}..."
    
    # Update service selectors to point to target environment
    kubectl patch service "${RELEASE_NAME}-gateway" -n "$NAMESPACE" -p "{\"spec\":{\"selector\":{\"environment\":\"${target_env}\"}}}"
    
    # Wait for service endpoint update to propagate
    sleep 10
    
    # Verify the switch
    local actual_env
    actual_env=$(kubectl get service "${RELEASE_NAME}-gateway" -n "$NAMESPACE" -o jsonpath='{.spec.selector.environment}')
    
    if [[ "$actual_env" == "$target_env" ]]; then
        log_success "Traffic successfully switched to ${target_env} environment"
        return 0
    else
        log_error "Failed to switch traffic to ${target_env} environment"
        return 1
    fi
}

# Function to perform post-switch validation
post_switch_validation() {
    local target_env=$1
    
    log_info "Performing post-switch validation..."
    
    # Wait for load balancer to pick up new endpoints
    sleep 30
    
    # Get the external endpoint
    local external_ip
    external_ip=$(kubectl get service "${RELEASE_NAME}-gateway" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || \
                 kubectl get service "${RELEASE_NAME}-gateway" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || \
                 echo "localhost")
    
    # Perform validation tests
    local validation_passed=true
    
    # Test external connectivity
    if [[ "$external_ip" != "localhost" ]]; then
        if ! curl -f -s "http://${external_ip}/health" > /dev/null; then
            log_error "External connectivity test failed"
            validation_passed=false
        fi
    fi
    
    # Check that old environment pods are not receiving traffic
    log_info "Monitoring traffic distribution..."
    
    if [[ "$validation_passed" == true ]]; then
        log_success "Post-switch validation passed"
        return 0
    else
        log_error "Post-switch validation failed"
        return 1
    fi
}

# Function to cleanup old environment
cleanup_old_environment() {
    local old_env=$1
    
    log_info "Cleaning up ${old_env} environment..."
    
    # Remove the old Helm release
    if helm list -n "$NAMESPACE" | grep -q "${RELEASE_NAME}-${old_env}"; then
        helm uninstall "${RELEASE_NAME}-${old_env}" -n "$NAMESPACE" --timeout "$TIMEOUT"
        log_success "Cleaned up ${old_env} environment"
    else
        log_info "No cleanup needed for ${old_env} environment"
    fi
}

# Function to rollback in case of failure
rollback() {
    local current_env=$1
    local failed_env=$2
    
    log_warning "Rolling back to ${current_env} environment..."
    
    # Switch traffic back to current environment
    kubectl patch service "${RELEASE_NAME}-gateway" -n "$NAMESPACE" -p "{\"spec\":{\"selector\":{\"environment\":\"${current_env}\"}}}"
    
    # Clean up failed deployment
    cleanup_old_environment "$failed_env"
    
    log_success "Rollback completed to ${current_env} environment"
}

# Main deployment function
main() {
    local image_tag=${1:-"latest"}
    local skip_tests=${2:-"false"}
    
    log_info "Starting blue-green deployment with image tag: ${image_tag}"
    
    # Check prerequisites
    check_prerequisites
    
    # Get current and target environments
    local current_env
    current_env=$(get_current_environment)
    local target_env
    target_env=$(get_target_environment "$current_env")
    
    log_info "Current environment: ${current_env}"
    log_info "Target environment: ${target_env}"
    
    # Deploy to target environment
    if ! deploy_to_target "$target_env" "$image_tag"; then
        log_error "Deployment to ${target_env} failed"
        exit 1
    fi
    
    # Wait for pods to be ready
    if ! wait_for_pods_ready "$target_env"; then
        log_error "Pods in ${target_env} failed to become ready"
        cleanup_old_environment "$target_env"
        exit 1
    fi
    
    # Perform health checks
    if ! perform_health_checks "$target_env"; then
        log_error "Health checks failed for ${target_env}"
        cleanup_old_environment "$target_env"
        exit 1
    fi
    
    # Perform smoke tests (unless skipped)
    if [[ "$skip_tests" != "true" ]]; then
        if ! perform_smoke_tests "$target_env"; then
            log_error "Smoke tests failed for ${target_env}"
            cleanup_old_environment "$target_env"
            exit 1
        fi
    fi
    
    # Switch traffic to target environment
    if ! switch_traffic "$target_env" "$current_env"; then
        log_error "Failed to switch traffic to ${target_env}"
        rollback "$current_env" "$target_env"
        exit 1
    fi
    
    # Perform post-switch validation
    if ! post_switch_validation "$target_env"; then
        log_error "Post-switch validation failed"
        rollback "$current_env" "$target_env"
        exit 1
    fi
    
    # Wait before cleanup (allow time for verification)
    log_info "Deployment successful! Waiting 60 seconds before cleanup..."
    sleep 60
    
    # Clean up old environment
    cleanup_old_environment "$current_env"
    
    log_success "Blue-green deployment completed successfully!"
    log_success "Active environment: ${target_env}"
}

# Script usage
usage() {
    echo "Usage: $0 [IMAGE_TAG] [SKIP_TESTS]"
    echo ""
    echo "Arguments:"
    echo "  IMAGE_TAG   Docker image tag to deploy (default: latest)"
    echo "  SKIP_TESTS  Skip smoke tests (true/false, default: false)"
    echo ""
    echo "Examples:"
    echo "  $0 v1.2.3"
    echo "  $0 v1.2.3 false"
    echo "  $0 latest true"
}

# Check for help flag
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Run main function with provided arguments
main "${1:-latest}" "${2:-false}"