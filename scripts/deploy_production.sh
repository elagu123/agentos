#!/bin/bash
set -euo pipefail

# AgentOS Production Deployment Script
# Comprehensive automated deployment with safety checks and rollback capabilities

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly ENVIRONMENT="${ENVIRONMENT:-production}"
readonly NAMESPACE="${NAMESPACE:-production}"
readonly CLUSTER_NAME="${CLUSTER_NAME:-agentos-production}"
readonly REGION="${REGION:-us-east-1}"
readonly REGISTRY="${REGISTRY:-ghcr.io}"
readonly IMAGE_NAME="${IMAGE_NAME:-agentos/api}"

# Default values
SKIP_TESTS="${SKIP_TESTS:-false}"
SKIP_SECURITY_SCAN="${SKIP_SECURITY_SCAN:-false}"
DRY_RUN="${DRY_RUN:-false}"
FORCE_DEPLOY="${FORCE_DEPLOY:-false}"
ROLLBACK_VERSION=""

# Logging functions
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
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

log_step() {
    echo -e "\n${PURPLE}[STEP]${NC} $1"
    echo -e "${BLUE}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
}

# Utility functions
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command '$1' not found"
        exit 1
    fi
}

confirm_action() {
    if [[ "$FORCE_DEPLOY" == "true" ]]; then
        return 0
    fi

    echo -e "${YELLOW}$1${NC}"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled by user"
        exit 0
    fi
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/agentos-deploy-*.tmp
}

# Error handler
error_handler() {
    local line_no=$1
    local error_code=$2
    log_error "Error occurred on line $line_no: exit code $error_code"
    cleanup
    exit $error_code
}

# Set error trap
trap 'error_handler ${LINENO} $?' ERR
trap cleanup EXIT

# Help function
show_help() {
    cat << EOF
AgentOS Production Deployment Script

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -v, --version VERSION   Deploy specific version (default: auto-generated)
    -e, --env ENVIRONMENT   Target environment (default: production)
    -n, --namespace NS      Kubernetes namespace (default: production)
    -c, --cluster CLUSTER   EKS cluster name (default: agentos-production)
    -r, --region REGION     AWS region (default: us-east-1)
    --skip-tests            Skip test execution
    --skip-security         Skip security scans
    --dry-run              Show what would be done without executing
    --force                 Skip confirmation prompts
    --rollback VERSION      Rollback to specific version

EXAMPLES:
    $0                      # Deploy latest version with all checks
    $0 --version v1.2.3     # Deploy specific version
    $0 --dry-run            # Preview deployment
    $0 --rollback v1.2.2    # Rollback to previous version
    $0 --skip-tests --force # Quick deployment without tests

ENVIRONMENT VARIABLES:
    ENVIRONMENT             Target environment
    NAMESPACE              Kubernetes namespace
    CLUSTER_NAME           EKS cluster name
    REGION                 AWS region
    SKIP_TESTS             Skip test execution
    SKIP_SECURITY_SCAN     Skip security scans
    DRY_RUN                Dry run mode
    FORCE_DEPLOY           Force deployment
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                VERSION="$2"
                shift 2
                ;;
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -c|--cluster)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            -r|--region)
                REGION="$2"
                shift 2
                ;;
            --skip-tests)
                SKIP_TESTS="true"
                shift
                ;;
            --skip-security)
                SKIP_SECURITY_SCAN="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --force)
                FORCE_DEPLOY="true"
                shift
                ;;
            --rollback)
                ROLLBACK_VERSION="$2"
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check required commands
    local required_commands=("docker" "kubectl" "aws" "git" "jq" "curl")
    for cmd in "${required_commands[@]}"; do
        check_command "$cmd"
    done

    # Check AWS credentials
    if ! aws sts get-caller-identity &>/dev/null; then
        log_error "AWS credentials not configured"
        exit 1
    fi

    # Check Docker daemon
    if ! docker info &>/dev/null; then
        log_error "Docker daemon not running"
        exit 1
    fi

    # Check Git repository
    if ! git rev-parse --git-dir &>/dev/null; then
        log_error "Not in a Git repository"
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# Generate version
generate_version() {
    if [[ -n "${VERSION:-}" ]]; then
        log_info "Using provided version: $VERSION"
        return
    fi

    # Generate version from date and git commit
    local date_part=$(date +%Y%m%d)
    local commit_hash=$(git rev-parse --short HEAD)
    local build_number="${GITHUB_RUN_NUMBER:-$(date +%s)}"

    VERSION="${date_part}-${build_number}-${commit_hash}"
    log_info "Generated version: $VERSION"
}

# Pre-deployment checks
run_pre_deployment_checks() {
    log_step "Running pre-deployment checks..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Skipping pre-deployment checks in dry-run mode"
        return
    fi

    # Run comprehensive pre-deployment validation
    if [[ -f "$PROJECT_ROOT/scripts/pre_deployment_check.py" ]]; then
        log_info "Running pre-deployment validation script..."
        cd "$PROJECT_ROOT"

        if ! python scripts/pre_deployment_check.py --env .env.production; then
            log_error "Pre-deployment checks failed"
            exit 1
        fi
    else
        log_warning "Pre-deployment check script not found"
    fi

    log_success "Pre-deployment checks passed"
}

# Run tests
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]] || [[ "$DRY_RUN" == "true" ]]; then
        log_info "Skipping tests"
        return
    fi

    log_step "Running test suite..."

    cd "$PROJECT_ROOT"

    # Install test dependencies
    if [[ -f "requirements-dev.txt" ]]; then
        pip install -r requirements-dev.txt
    fi

    # Run tests with coverage
    if ! python -m pytest tests/ --cov=app --cov-report=term --maxfail=5; then
        log_error "Tests failed"
        exit 1
    fi

    log_success "All tests passed"
}

# Security scan
run_security_scan() {
    if [[ "$SKIP_SECURITY_SCAN" == "true" ]] || [[ "$DRY_RUN" == "true" ]]; then
        log_info "Skipping security scan"
        return
    fi

    log_step "Running security scan..."

    cd "$PROJECT_ROOT"

    # Run Bandit security linter
    if command -v bandit &> /dev/null; then
        log_info "Running Bandit security scan..."
        bandit -r app/ -ll
    fi

    # Run safety check
    if command -v safety &> /dev/null; then
        log_info "Checking for known vulnerabilities..."
        safety check
    fi

    log_success "Security scan completed"
}

# Build and push Docker images
build_and_push_images() {
    log_step "Building and pushing Docker images..."

    cd "$PROJECT_ROOT"

    local image_tag="$REGISTRY/$IMAGE_NAME:$VERSION"
    local latest_tag="$REGISTRY/$IMAGE_NAME:latest"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would build and push: $image_tag"
        return
    fi

    # Build image
    log_info "Building Docker image..."
    docker build \
        -f Dockerfile.production \
        -t "$image_tag" \
        -t "$latest_tag" \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse HEAD)" \
        --build-arg VERSION="$VERSION" \
        .

    # Push images
    log_info "Pushing Docker images..."
    docker push "$image_tag"
    docker push "$latest_tag"

    log_success "Images built and pushed successfully"
}

# Update Kubernetes configuration
update_kubeconfig() {
    log_step "Updating Kubernetes configuration..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would update kubeconfig for cluster: $CLUSTER_NAME"
        return
    fi

    # Update kubeconfig
    aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

    # Verify connection
    if ! kubectl cluster-info &>/dev/null; then
        log_error "Failed to connect to Kubernetes cluster"
        exit 1
    fi

    # Check namespace
    if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_warning "Namespace $NAMESPACE does not exist, creating..."
        kubectl create namespace "$NAMESPACE"
    fi

    log_success "Kubernetes configuration updated"
}

# Deploy to Kubernetes
deploy_to_kubernetes() {
    log_step "Deploying to Kubernetes..."

    cd "$PROJECT_ROOT"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would deploy to namespace: $NAMESPACE"
        log_info "Would use image: $REGISTRY/$IMAGE_NAME:$VERSION"
        return
    fi

    # Apply Kubernetes manifests
    log_info "Applying Kubernetes manifests..."
    kubectl apply -f k8s/production/namespace.yaml
    kubectl apply -f k8s/production/configmap.yaml

    # Handle secrets separately (don't overwrite existing ones)
    if ! kubectl get secret agentos-secrets -n "$NAMESPACE" &>/dev/null; then
        log_warning "Secrets not found, you may need to create them manually"
    fi

    kubectl apply -f k8s/production/deployment.yaml
    kubectl apply -f k8s/production/ingress.yaml

    # Update image
    log_info "Updating deployment image..."
    kubectl set image deployment/agentos-api \
        api="$REGISTRY/$IMAGE_NAME:$VERSION" \
        -n "$NAMESPACE"

    # Wait for rollout
    log_info "Waiting for deployment rollout..."
    kubectl rollout status deployment/agentos-api -n "$NAMESPACE" --timeout=600s

    log_success "Deployment completed successfully"
}

# Verify deployment
verify_deployment() {
    log_step "Verifying deployment..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would verify deployment"
        return
    fi

    # Check deployment status
    log_info "Checking deployment status..."
    kubectl get deployments -n "$NAMESPACE"
    kubectl get pods -n "$NAMESPACE"
    kubectl get services -n "$NAMESPACE"

    # Check pod health
    local pod_count=$(kubectl get pods -n "$NAMESPACE" -l app=agentos --no-headers | wc -l)
    local ready_count=$(kubectl get pods -n "$NAMESPACE" -l app=agentos --no-headers | grep -c "Running" || true)

    if [[ "$ready_count" -eq 0 ]]; then
        log_error "No pods are running"
        kubectl logs -l app=agentos -n "$NAMESPACE" --tail=50
        exit 1
    fi

    log_info "Pods status: $ready_count/$pod_count ready"

    # Get service endpoint
    local api_endpoint=""
    if kubectl get ingress agentos-ingress -n "$NAMESPACE" &>/dev/null; then
        api_endpoint=$(kubectl get ingress agentos-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")
    fi

    if [[ -n "$api_endpoint" ]]; then
        log_info "API endpoint: https://$api_endpoint"

        # Basic health check
        log_info "Running health check..."
        if curl -f "https://$api_endpoint/health" &>/dev/null; then
            log_success "Health check passed"
        else
            log_warning "Health check failed - service may still be starting"
        fi
    fi

    log_success "Deployment verification completed"
}

# Run smoke tests
run_smoke_tests() {
    log_step "Running smoke tests..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would run smoke tests"
        return
    fi

    cd "$PROJECT_ROOT"

    # Get API endpoint
    local api_endpoint=""
    if kubectl get ingress agentos-ingress -n "$NAMESPACE" &>/dev/null; then
        api_endpoint=$(kubectl get ingress agentos-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")
    fi

    if [[ -z "$api_endpoint" ]]; then
        log_warning "Could not determine API endpoint, skipping smoke tests"
        return
    fi

    # Run smoke tests
    if [[ -f "scripts/smoke_tests.py" ]]; then
        log_info "Running smoke tests against https://$api_endpoint"

        if python scripts/smoke_tests.py --endpoint "https://$api_endpoint"; then
            log_success "Smoke tests passed"
        else
            log_error "Smoke tests failed"
            exit 1
        fi
    else
        log_warning "Smoke test script not found"
    fi
}

# Post-deployment tasks
post_deployment_tasks() {
    log_step "Running post-deployment tasks..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would run post-deployment tasks"
        return
    fi

    # Update deployment record
    local deployment_record="/tmp/agentos-deploy-${VERSION}.tmp"
    cat > "$deployment_record" << EOF
{
  "version": "$VERSION",
  "environment": "$ENVIRONMENT",
  "namespace": "$NAMESPACE",
  "cluster": "$CLUSTER_NAME",
  "deployed_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "deployed_by": "${USER:-unknown}",
  "git_commit": "$(git rev-parse HEAD)",
  "git_branch": "$(git rev-parse --abbrev-ref HEAD)"
}
EOF

    log_info "Deployment record created: $deployment_record"

    # Notify team (if webhook configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        log_info "Sending Slack notification..."
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚀 AgentOS deployed to $ENVIRONMENT\\nVersion: $VERSION\\nBy: ${USER:-unknown}\"}" \
            "$SLACK_WEBHOOK_URL" || log_warning "Failed to send Slack notification"
    fi

    log_success "Post-deployment tasks completed"
}

# Rollback function
rollback_deployment() {
    if [[ -z "$ROLLBACK_VERSION" ]]; then
        log_error "Rollback version not specified"
        exit 1
    fi

    log_step "Rolling back to version: $ROLLBACK_VERSION"

    confirm_action "This will rollback the deployment to $ROLLBACK_VERSION. This action cannot be undone."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would rollback to: $ROLLBACK_VERSION"
        return
    fi

    # Update kubeconfig
    update_kubeconfig

    # Rollback deployment
    log_info "Rolling back deployment..."
    kubectl set image deployment/agentos-api \
        api="$REGISTRY/$IMAGE_NAME:$ROLLBACK_VERSION" \
        -n "$NAMESPACE"

    # Wait for rollback
    log_info "Waiting for rollback to complete..."
    kubectl rollout status deployment/agentos-api -n "$NAMESPACE" --timeout=600s

    # Verify rollback
    verify_deployment

    log_success "Rollback completed successfully"
    exit 0
}

# Main deployment function
main() {
    echo -e "${CYAN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════╗
    ║          AgentOS Production Deployment        ║
    ║              Automated Pipeline               ║
    ╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    # Parse arguments
    parse_args "$@"

    # Handle rollback
    if [[ -n "$ROLLBACK_VERSION" ]]; then
        rollback_deployment
        return
    fi

    # Show configuration
    log_info "Deployment Configuration:"
    log_info "  Environment: $ENVIRONMENT"
    log_info "  Namespace: $NAMESPACE"
    log_info "  Cluster: $CLUSTER_NAME"
    log_info "  Region: $REGION"
    log_info "  Dry Run: $DRY_RUN"
    log_info "  Skip Tests: $SKIP_TESTS"
    log_info "  Skip Security: $SKIP_SECURITY_SCAN"

    # Confirm deployment
    if [[ "$ENVIRONMENT" == "production" ]]; then
        confirm_action "⚠️  You are about to deploy to PRODUCTION. This will affect live users."
    fi

    # Execute deployment pipeline
    check_prerequisites
    generate_version
    run_pre_deployment_checks
    run_tests
    run_security_scan
    build_and_push_images
    update_kubeconfig
    deploy_to_kubernetes
    verify_deployment
    run_smoke_tests
    post_deployment_tasks

    # Success message
    echo -e "\n${GREEN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════╗
    ║            DEPLOYMENT SUCCESSFUL!             ║
    ║                                               ║
    ║  🚀 AgentOS is now running in production      ║
    ║                                               ║
    ╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    log_success "Deployment completed successfully!"
    log_info "Version: $VERSION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Time: $(date)"

    # Show useful links
    echo -e "\n${BLUE}Useful Links:${NC}"
    echo "• 🌐 Application: https://app.agentos.io"
    echo "• 🔌 API Health: https://api.agentos.io/health"
    echo "• 📊 Monitoring: https://app.datadoghq.com"
    echo "• 🐛 Error Tracking: https://sentry.io"
    echo "• 📈 Metrics: https://api.agentos.io/metrics"
}

# Execute main function
main "$@"