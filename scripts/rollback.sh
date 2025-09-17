#!/bin/bash
set -euo pipefail

# AgentOS Emergency Rollback Script
# Quick rollback to previous version with safety checks

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

# Variables
ROLLBACK_VERSION=""
FORCE_ROLLBACK="${FORCE_ROLLBACK:-false}"
DRY_RUN="${DRY_RUN:-false}"
SKIP_VERIFICATION="${SKIP_VERIFICATION:-false}"

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
    if [[ "$FORCE_ROLLBACK" == "true" ]]; then
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

# Help function
show_help() {
    cat << EOF
AgentOS Emergency Rollback Script

Usage: $0 [OPTIONS] <VERSION>

ARGUMENTS:
    VERSION                 Version to rollback to (required)

OPTIONS:
    -h, --help              Show this help message
    -e, --env ENVIRONMENT   Target environment (default: production)
    -n, --namespace NS      Kubernetes namespace (default: production)
    -c, --cluster CLUSTER   EKS cluster name (default: agentos-production)
    -r, --region REGION     AWS region (default: us-east-1)
    --force                 Skip confirmation prompts
    --dry-run              Show what would be done without executing
    --skip-verification     Skip post-rollback verification
    --list-versions         List available versions to rollback to

EXAMPLES:
    $0 20241201-123-abc123      # Rollback to specific version
    $0 --list-versions          # Show available versions
    $0 --dry-run v1.2.3         # Preview rollback
    $0 --force v1.2.2           # Force rollback without confirmation

EMERGENCY USAGE:
    # Quick rollback to previous version
    $0 \$(kubectl rollout history deployment/agentos-api -n production | tail -2 | head -1 | awk '{print \$1}')

ENVIRONMENT VARIABLES:
    ENVIRONMENT             Target environment
    NAMESPACE              Kubernetes namespace
    CLUSTER_NAME           EKS cluster name
    REGION                 AWS region
    FORCE_ROLLBACK         Skip confirmations
    DRY_RUN                Dry run mode
    SKIP_VERIFICATION      Skip verification steps
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
            --force)
                FORCE_ROLLBACK="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --skip-verification)
                SKIP_VERIFICATION="true"
                shift
                ;;
            --list-versions)
                list_available_versions
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$ROLLBACK_VERSION" ]]; then
                    ROLLBACK_VERSION="$1"
                else
                    log_error "Too many arguments"
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$ROLLBACK_VERSION" ]]; then
        log_error "Rollback version is required"
        show_help
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check required commands
    local required_commands=("kubectl" "aws" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        check_command "$cmd"
    done

    # Check AWS credentials
    if ! aws sts get-caller-identity &>/dev/null; then
        log_error "AWS credentials not configured"
        exit 1
    fi

    log_success "All prerequisites satisfied"
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
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi

    log_success "Kubernetes configuration updated"
}

# List available versions
list_available_versions() {
    log_step "Listing available versions..."

    update_kubeconfig

    echo -e "\n${BLUE}Available versions for rollback:${NC}"
    echo -e "${BLUE}================================${NC}"

    # Get current version
    local current_version=$(kubectl get deployment agentos-api -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}' | sed 's/.*://')
    echo -e "${GREEN}Current version: $current_version${NC}"

    # Get rollout history
    echo -e "\n${YELLOW}Recent deployments:${NC}"
    kubectl rollout history deployment/agentos-api -n "$NAMESPACE"

    # Get available image tags from registry (if accessible)
    echo -e "\n${YELLOW}Available image tags:${NC}"
    if command -v skopeo &> /dev/null; then
        skopeo list-tags "docker://$REGISTRY/$IMAGE_NAME" 2>/dev/null | jq -r '.Tags[]' | sort -r | head -10
    else
        log_info "Install 'skopeo' to see all available image tags"
    fi
}

# Get current deployment state
get_current_state() {
    log_step "Getting current deployment state..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would get current deployment state"
        return
    fi

    # Get current deployment info
    local current_image=$(kubectl get deployment agentos-api -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')
    local current_version=$(echo "$current_image" | sed 's/.*://')
    local current_replicas=$(kubectl get deployment agentos-api -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
    local ready_replicas=$(kubectl get deployment agentos-api -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')

    log_info "Current Deployment State:"
    log_info "  Image: $current_image"
    log_info "  Version: $current_version"
    log_info "  Desired Replicas: $current_replicas"
    log_info "  Ready Replicas: ${ready_replicas:-0}"

    # Save current state for potential rollback
    cat > "/tmp/agentos-rollback-state.json" << EOF
{
  "previous_image": "$current_image",
  "previous_version": "$current_version",
  "rollback_image": "$REGISTRY/$IMAGE_NAME:$ROLLBACK_VERSION",
  "rollback_version": "$ROLLBACK_VERSION",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "performed_by": "${USER:-unknown}"
}
EOF

    log_info "Current state saved to /tmp/agentos-rollback-state.json"
}

# Verify rollback version exists
verify_rollback_version() {
    log_step "Verifying rollback version exists..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would verify version: $ROLLBACK_VERSION"
        return
    fi

    local image_url="$REGISTRY/$IMAGE_NAME:$ROLLBACK_VERSION"

    # Try to pull image manifest (without downloading)
    if docker manifest inspect "$image_url" &>/dev/null; then
        log_success "Version $ROLLBACK_VERSION exists and is accessible"
    elif skopeo inspect "docker://$image_url" &>/dev/null 2>&1; then
        log_success "Version $ROLLBACK_VERSION exists and is accessible"
    else
        log_error "Version $ROLLBACK_VERSION does not exist or is not accessible"
        log_error "Image URL: $image_url"
        exit 1
    fi
}

# Create backup point
create_backup_point() {
    log_step "Creating backup point..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would create backup point"
        return
    fi

    # Annotate deployment with backup info
    kubectl annotate deployment agentos-api -n "$NAMESPACE" \
        "rollback.agentos.io/backup-timestamp=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        "rollback.agentos.io/backup-performed-by=${USER:-unknown}" \
        --overwrite

    log_success "Backup point created"
}

# Perform rollback
perform_rollback() {
    log_step "Performing rollback to version: $ROLLBACK_VERSION"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would rollback to: $REGISTRY/$IMAGE_NAME:$ROLLBACK_VERSION"
        return
    fi

    # Final confirmation for production
    if [[ "$ENVIRONMENT" == "production" ]]; then
        confirm_action "⚠️  EMERGENCY ROLLBACK: This will immediately change the production environment to version $ROLLBACK_VERSION."
    fi

    # Update deployment image
    log_info "Updating deployment image..."
    kubectl set image deployment/agentos-api \
        api="$REGISTRY/$IMAGE_NAME:$ROLLBACK_VERSION" \
        -n "$NAMESPACE"

    # Add rollback annotations
    kubectl annotate deployment agentos-api -n "$NAMESPACE" \
        "rollback.agentos.io/timestamp=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        "rollback.agentos.io/version=$ROLLBACK_VERSION" \
        "rollback.agentos.io/performed-by=${USER:-unknown}" \
        --overwrite

    # Wait for rollback to complete
    log_info "Waiting for rollback to complete..."
    if ! kubectl rollout status deployment/agentos-api -n "$NAMESPACE" --timeout=600s; then
        log_error "Rollback failed or timed out"

        # Show pod status for debugging
        log_error "Current pod status:"
        kubectl get pods -n "$NAMESPACE" -l app=agentos

        # Show recent events
        log_error "Recent events:"
        kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' | tail -10

        exit 1
    fi

    log_success "Rollback completed successfully"
}

# Verify rollback
verify_rollback() {
    if [[ "$SKIP_VERIFICATION" == "true" ]]; then
        log_info "Skipping rollback verification"
        return
    fi

    log_step "Verifying rollback..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would verify rollback"
        return
    fi

    # Check deployment status
    log_info "Checking deployment status..."
    kubectl get deployment agentos-api -n "$NAMESPACE"

    # Check pod status
    local pod_count=$(kubectl get pods -n "$NAMESPACE" -l app=agentos --no-headers | wc -l)
    local ready_count=$(kubectl get pods -n "$NAMESPACE" -l app=agentos --no-headers | grep -c "Running" || true)

    log_info "Pod status: $ready_count/$pod_count ready"

    if [[ "$ready_count" -eq 0 ]]; then
        log_error "No pods are running after rollback"
        kubectl logs -l app=agentos -n "$NAMESPACE" --tail=50
        exit 1
    fi

    # Verify correct image version
    local current_image=$(kubectl get deployment agentos-api -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')
    local expected_image="$REGISTRY/$IMAGE_NAME:$ROLLBACK_VERSION"

    if [[ "$current_image" == "$expected_image" ]]; then
        log_success "Image version verified: $current_image"
    else
        log_error "Image version mismatch. Expected: $expected_image, Got: $current_image"
        exit 1
    fi

    # Basic health check
    log_info "Performing health check..."
    local api_endpoint=""
    if kubectl get ingress agentos-ingress -n "$NAMESPACE" &>/dev/null; then
        api_endpoint=$(kubectl get ingress agentos-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")
    fi

    if [[ -n "$api_endpoint" ]]; then
        # Wait a bit for service to be ready
        log_info "Waiting for service to be ready..."
        sleep 30

        if curl -f "https://$api_endpoint/health" --max-time 10 &>/dev/null; then
            log_success "Health check passed"
        else
            log_warning "Health check failed - service may still be starting"
            log_info "Manual verification may be required"
        fi
    else
        log_warning "Could not determine API endpoint for health check"
    fi

    log_success "Rollback verification completed"
}

# Post-rollback tasks
post_rollback_tasks() {
    log_step "Running post-rollback tasks..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "Would run post-rollback tasks"
        return
    fi

    # Notify team (if webhook configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        log_info "Sending Slack notification..."
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🔄 AgentOS rollback completed\\nRolled back to: $ROLLBACK_VERSION\\nBy: ${USER:-unknown}\\nEnvironment: $ENVIRONMENT\"}" \
            "$SLACK_WEBHOOK_URL" || log_warning "Failed to send Slack notification"
    fi

    # Log rollback event
    log_info "Rollback completed successfully"
    log_info "Version: $ROLLBACK_VERSION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Time: $(date)"

    log_success "Post-rollback tasks completed"
}

# Main rollback function
main() {
    echo -e "${RED}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════╗
    ║          AgentOS Emergency Rollback           ║
    ║             ⚠️  CAUTION REQUIRED ⚠️            ║
    ╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    # Parse arguments
    parse_args "$@"

    # Show configuration
    log_info "Rollback Configuration:"
    log_info "  Target Version: $ROLLBACK_VERSION"
    log_info "  Environment: $ENVIRONMENT"
    log_info "  Namespace: $NAMESPACE"
    log_info "  Cluster: $CLUSTER_NAME"
    log_info "  Region: $REGION"
    log_info "  Dry Run: $DRY_RUN"
    log_info "  Force: $FORCE_ROLLBACK"

    # Execute rollback pipeline
    check_prerequisites
    update_kubeconfig
    get_current_state
    verify_rollback_version
    create_backup_point
    perform_rollback
    verify_rollback
    post_rollback_tasks

    # Success message
    echo -e "\n${GREEN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════╗
    ║            ROLLBACK SUCCESSFUL!               ║
    ║                                               ║
    ║  🔄 AgentOS has been rolled back              ║
    ║                                               ║
    ╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    log_success "Rollback completed successfully!"
    log_info "Rolled back to version: $ROLLBACK_VERSION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Time: $(date)"

    # Show useful links
    echo -e "\n${BLUE}Verify the rollback:${NC}"
    echo "• 🌐 Application: https://app.agentos.io"
    echo "• 🔌 API Health: https://api.agentos.io/health"
    echo "• 📊 Monitoring: https://app.datadoghq.com"
    echo "• 🐛 Error Tracking: https://sentry.io"

    # Show next steps
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Verify application functionality"
    echo "2. Monitor error rates and performance"
    echo "3. Investigate root cause of issues that required rollback"
    echo "4. Plan forward deployment with fixes"
}

# Execute main function
main "$@"