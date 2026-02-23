#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# AnvilOps Platform Destroy Script
#
# Tears down Kubernetes resources and Terraform-managed infrastructure.
#
# Usage: ./destroy.sh <environment> [--include-state-backend] [--force]
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
K8S_DIR="${PLATFORM_DIR}/k8s"
TF_DIR="${PLATFORM_DIR}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()    { echo -e "${CYAN}[STEP]${NC}  $*"; }

usage() {
    echo "Usage: $(basename "$0") <environment> [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --include-state-backend  Also destroy the Terraform state backend"
    echo "  --force                  Skip interactive confirmations"
    echo ""
    echo "WARNING: This action is irreversible."
    exit 1
}

ENV=""
INCLUDE_STATE_BACKEND=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        dev|staging|production) ENV="$1"; shift ;;
        --include-state-backend) INCLUDE_STATE_BACKEND=true; shift ;;
        --force) FORCE=true; shift ;;
        -h|--help) usage ;;
        *) log_error "Unknown argument: $1"; usage ;;
    esac
done

if [[ -z "$ENV" ]]; then log_error "Environment is required."; usage; fi

confirm_destruction() {
    if [[ "$FORCE" == "true" ]]; then return 0; fi

    echo ""
    echo -e "${RED}============================================================${NC}"
    echo -e "${RED}  DANGER: You are about to DESTROY the ${ENV} environment  ${NC}"
    echo -e "${RED}============================================================${NC}"
    echo ""
    echo -e "${YELLOW}Type the environment name '${ENV}' to confirm:${NC}"
    read -rp "> " confirm
    if [[ "$confirm" != "$ENV" ]]; then
        log_error "Confirmation failed."
        exit 1
    fi

    if [[ "$ENV" == "production" ]]; then
        echo -e "${RED}Type 'DESTROY PRODUCTION' to proceed:${NC}"
        read -rp "> " second_confirm
        if [[ "$second_confirm" != "DESTROY PRODUCTION" ]]; then
            log_error "Second confirmation failed."
            exit 1
        fi
    fi
}

remove_k8s_resources() {
    log_step "Removing Kubernetes resources..."

    if ! kubectl cluster-info &>/dev/null; then
        log_warn "Cannot reach cluster. Skipping K8s removal."
        return 0
    fi

    local overlay_dir="${K8S_DIR}/overlays/${ENV}"
    if [[ -d "$overlay_dir" ]]; then
        kustomize build "$overlay_dir" | kubectl delete --ignore-not-found -f - || true
    fi

    kubectl delete namespace anvilops --timeout=120s 2>/dev/null || true

    # Uninstall Helm charts in reverse dependency order
    log_info "Uninstalling KEDA..."
    helm uninstall keda -n keda 2>/dev/null || true

    log_info "Uninstalling Cluster Autoscaler..."
    helm uninstall cluster-autoscaler -n kube-system 2>/dev/null || true

    log_info "Uninstalling External DNS..."
    helm uninstall external-dns -n external-dns 2>/dev/null || true

    log_info "Uninstalling Metrics Server..."
    helm uninstall metrics-server -n kube-system 2>/dev/null || true

    log_info "Uninstalling External Secrets..."
    helm uninstall external-secrets -n external-secrets 2>/dev/null || true

    log_info "Uninstalling AWS Load Balancer Controller..."
    helm uninstall aws-load-balancer-controller -n kube-system 2>/dev/null || true

    # Clean up namespaces created by Helm charts
    log_info "Deleting chart namespaces..."
    kubectl delete namespace keda --ignore-not-found --timeout=60s || true
    kubectl delete namespace external-dns --ignore-not-found --timeout=60s || true
    kubectl delete namespace external-secrets --ignore-not-found --timeout=60s || true

    log_success "Kubernetes resources removed."
}

run_terraform_destroy() {
    log_step "Running Terraform destroy for ${ENV}..."

    pushd "$TF_DIR" >/dev/null

    terraform init -input=false -reconfigure \
        -backend-config="key=anvilops/platform/${ENV}/terraform.tfstate" || true

    terraform workspace select "$ENV" 2>/dev/null || true

    terraform plan -destroy -out=tfplan-destroy -input=false -var="environment=${ENV}" || {
        log_warn "Plan failed. Attempting direct destroy..."
        terraform destroy -auto-approve -var="environment=${ENV}" || true
        popd >/dev/null
        return
    }

    if [[ "$FORCE" != "true" ]]; then
        read -rp "Proceed with destruction? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            rm -f tfplan-destroy
            popd >/dev/null
            exit 1
        fi
    fi

    terraform apply -input=false tfplan-destroy
    rm -f tfplan-destroy

    terraform workspace select default 2>/dev/null || true
    terraform workspace delete "$ENV" 2>/dev/null || true

    popd >/dev/null
    log_success "Terraform destroy complete for ${ENV}."
}

destroy_state_backend() {
    if [[ "$INCLUDE_STATE_BACKEND" != "true" ]]; then return 0; fi

    log_step "Destroying Terraform state backend..."

    if [[ "$FORCE" != "true" ]]; then
        log_warn "This will make ALL Terraform state inaccessible."
        read -rp "Are you sure? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then return 0; fi
    fi

    local state_backend_dir="${TF_DIR}/modules/state-backend"
    if [[ ! -d "$state_backend_dir" ]]; then
        log_warn "State backend directory not found."
        return 0
    fi

    pushd "$state_backend_dir" >/dev/null
    terraform init -input=false
    terraform destroy -auto-approve
    popd >/dev/null

    log_success "State backend destroyed."
}

main() {
    echo ""
    log_info "=========================================="
    log_info "  AnvilOps Platform Destroy"
    log_info "  Environment: ${ENV}"
    log_info "=========================================="
    echo ""

    confirm_destruction
    echo ""
    remove_k8s_resources
    echo ""
    run_terraform_destroy
    echo ""
    destroy_state_backend

    echo ""
    log_success "=========================================="
    log_success "  Destroy complete for ${ENV}."
    log_success "=========================================="
}

main
