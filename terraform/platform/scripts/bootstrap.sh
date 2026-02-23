#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# AnvilOps Platform Bootstrap Script
#
# Provisions the EKS cluster via Terraform, installs required Helm charts,
# and applies Kustomize overlays for the target environment.
#
# Usage: ./bootstrap.sh [dev|staging|production]
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
    echo "Usage: $(basename "$0") [dev|staging|production]"
    echo ""
    echo "Bootstrap the AnvilOps platform for the specified environment."
    echo ""
    echo "Prerequisites: aws, terraform, kubectl, helm, kustomize"
    exit 1
}

check_prerequisites() {
    log_step "Checking prerequisites..."
    local missing=0

    for cmd in aws terraform kubectl helm kustomize; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Required command not found: $cmd"
            missing=$((missing + 1))
        else
            log_success "$cmd found"
        fi
    done

    if [[ $missing -gt 0 ]]; then
        log_error "$missing prerequisite(s) missing."
        exit 1
    fi

    if ! aws sts get-caller-identity &>/dev/null; then
        log_error "AWS credentials not configured or expired."
        exit 1
    fi
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)
    log_success "AWS authenticated: account $account_id"
}

init_state_backend() {
    log_step "Initializing Terraform state backend..."

    local state_backend_dir="${TF_DIR}/modules/state-backend"
    if [[ ! -d "$state_backend_dir" ]]; then
        log_warn "State backend module not found. Skipping."
        return 0
    fi

    pushd "$state_backend_dir" >/dev/null
    terraform init -input=false
    terraform plan -out=tfplan -input=false
    terraform apply -input=false tfplan
    rm -f tfplan
    popd >/dev/null

    log_success "State backend initialized."
}

run_terraform() {
    local env="$1"
    log_step "Running Terraform for environment: ${env}"

    pushd "$TF_DIR" >/dev/null

    terraform init -input=false -reconfigure \
        -backend-config="key=anvilops/platform/${env}/terraform.tfstate"

    terraform workspace select "$env" 2>/dev/null || terraform workspace new "$env"

    log_info "Running terraform plan..."
    terraform plan -out=tfplan -input=false -var="environment=${env}"

    echo ""
    log_warn "Review the plan above carefully."
    read -rp "Apply this plan? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_error "Aborted by user."
        rm -f tfplan
        popd >/dev/null
        exit 1
    fi

    terraform apply -input=false tfplan
    rm -f tfplan
    popd >/dev/null
    log_success "Terraform apply complete for ${env}."
}

update_kubeconfig() {
    local env="$1"
    log_step "Updating kubeconfig for EKS cluster..."

    local cluster_name="anvilops-${env}"
    local region
    region=$(aws configure get region 2>/dev/null || echo "us-east-1")

    aws eks update-kubeconfig --name "$cluster_name" --region "$region" --alias "$cluster_name"

    if kubectl cluster-info &>/dev/null; then
        log_success "Connected to EKS cluster: ${cluster_name}"
    else
        log_error "Failed to connect to EKS cluster: ${cluster_name}"
        exit 1
    fi
}

install_helm_charts() {
    local env="$1"
    log_step "Installing Helm charts..."

    # -------------------------------------------------------------------------
    # Gather variables from Terraform outputs and environment
    # -------------------------------------------------------------------------
    local cluster_name="anvilops-${env}"
    local region
    region=$(aws configure get region 2>/dev/null || echo "us-east-1")

    local vpc_id alb_role_arn extdns_role_arn autoscaler_role_arn domain

    pushd "$TF_DIR" > /dev/null
    vpc_id=$(terraform output -raw vpc_id 2>/dev/null || echo "")
    alb_role_arn=$(terraform output -raw alb_controller_role_arn 2>/dev/null || echo "")
    extdns_role_arn=$(terraform output -raw external_dns_role_arn 2>/dev/null || echo "")
    autoscaler_role_arn=$(terraform output -raw cluster_autoscaler_role_arn 2>/dev/null || echo "")
    domain=$(terraform output -raw domain_name 2>/dev/null || echo "")
    popd > /dev/null

    # Allow override via ANVILOPS_DOMAIN environment variable
    domain="${ANVILOPS_DOMAIN:-$domain}"

    if [[ -z "$vpc_id" ]]; then
        log_warn "vpc_id not available from Terraform outputs. ALB Controller may not function correctly."
    fi
    if [[ -z "$alb_role_arn" ]]; then
        log_warn "alb_controller_role_arn not available. ALB Controller will run without IRSA."
    fi
    if [[ -z "$extdns_role_arn" ]]; then
        log_warn "external_dns_role_arn not available. External DNS will run without IRSA."
    fi
    if [[ -z "$autoscaler_role_arn" ]]; then
        log_warn "cluster_autoscaler_role_arn not available. Cluster Autoscaler will run without IRSA."
    fi
    if [[ -z "$domain" ]]; then
        log_warn "Domain not set (no Terraform output and ANVILOPS_DOMAIN is unset). External DNS domain filter will be skipped."
    fi

    # -------------------------------------------------------------------------
    # Add all required Helm repositories
    # -------------------------------------------------------------------------
    log_info "Adding Helm repositories..."
    helm repo add eks https://aws.github.io/eks-charts 2>/dev/null || true
    helm repo add external-secrets https://charts.external-secrets.io 2>/dev/null || true
    helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/ 2>/dev/null || true
    helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ 2>/dev/null || true
    helm repo add autoscaler https://kubernetes.github.io/autoscaler 2>/dev/null || true
    helm repo add keda https://kedacore.github.io/charts 2>/dev/null || true
    helm repo update
    log_success "Helm repositories updated."

    # -------------------------------------------------------------------------
    # 1. AWS Load Balancer Controller (kube-system, with IRSA)
    # -------------------------------------------------------------------------
    log_info "Installing AWS Load Balancer Controller..."
    local alb_args=(
        --namespace kube-system
        --set clusterName="${cluster_name}"
        --set serviceAccount.create=true
        --set serviceAccount.name=aws-load-balancer-controller
        --set region="${region}"
    )
    if [[ -n "$vpc_id" ]]; then
        alb_args+=(--set vpcId="${vpc_id}")
    fi
    if [[ -n "$alb_role_arn" ]]; then
        alb_args+=(--set "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=${alb_role_arn}")
    fi
    helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
        "${alb_args[@]}" \
        --wait --timeout 5m
    log_success "AWS Load Balancer Controller installed."

    # -------------------------------------------------------------------------
    # 2. External Secrets Operator (external-secrets namespace)
    # -------------------------------------------------------------------------
    log_info "Installing External Secrets Operator..."
    helm upgrade --install external-secrets external-secrets/external-secrets \
        --namespace external-secrets --create-namespace \
        --set installCRDs=true \
        --wait --timeout 5m
    log_success "External Secrets Operator installed."

    # -------------------------------------------------------------------------
    # 3. External DNS (external-dns namespace, with IRSA)
    # -------------------------------------------------------------------------
    log_info "Installing External DNS..."
    local extdns_args=(
        --namespace external-dns --create-namespace
        --set provider.name=aws
        --set policy=sync
        --set registry=txt
        --set txtOwnerId="${cluster_name}"
    )
    if [[ -n "$domain" ]]; then
        extdns_args+=(--set "domainFilters[0]=${domain}")
    fi
    if [[ -n "$extdns_role_arn" ]]; then
        extdns_args+=(--set "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=${extdns_role_arn}")
    fi
    helm upgrade --install external-dns external-dns/external-dns \
        "${extdns_args[@]}" \
        --wait --timeout 5m
    log_success "External DNS installed."

    # -------------------------------------------------------------------------
    # 4. Metrics Server (kube-system)
    # -------------------------------------------------------------------------
    log_info "Installing Metrics Server..."
    helm upgrade --install metrics-server metrics-server/metrics-server \
        --namespace kube-system \
        --wait --timeout 5m
    log_success "Metrics Server installed."

    # -------------------------------------------------------------------------
    # 5. Cluster Autoscaler (kube-system, with IRSA)
    # -------------------------------------------------------------------------
    log_info "Installing Cluster Autoscaler..."
    local autoscaler_args=(
        --namespace kube-system
        --set autoDiscovery.clusterName="${cluster_name}"
        --set awsRegion="${region}"
        --set rbac.serviceAccount.create=true
        --set rbac.serviceAccount.name=cluster-autoscaler
    )
    if [[ -n "$autoscaler_role_arn" ]]; then
        autoscaler_args+=(--set "rbac.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=${autoscaler_role_arn}")
    fi
    helm upgrade --install cluster-autoscaler autoscaler/cluster-autoscaler \
        "${autoscaler_args[@]}" \
        --wait --timeout 5m
    log_success "Cluster Autoscaler installed."

    # -------------------------------------------------------------------------
    # 6. KEDA (keda namespace)
    # -------------------------------------------------------------------------
    log_info "Installing KEDA..."
    helm upgrade --install keda keda/keda \
        --namespace keda --create-namespace \
        --wait --timeout 10m
    log_success "KEDA installed."
}

apply_kustomize() {
    local env="$1"
    log_step "Applying Kustomize overlays for ${env}..."

    local overlay_dir="${K8S_DIR}/overlays/${env}"
    if [[ ! -d "$overlay_dir" ]]; then
        log_error "Overlay directory not found: ${overlay_dir}"
        exit 1
    fi

    log_info "Dry-run validation..."
    kustomize build "$overlay_dir" | kubectl apply --dry-run=server -f -

    log_info "Applying manifests..."
    kustomize build "$overlay_dir" | kubectl apply -f -

    log_info "Waiting for deployments..."
    kubectl rollout status deployment/anvilops-api -n anvilops --timeout=300s
    kubectl rollout status deployment/anvilops-worker -n anvilops --timeout=300s
    kubectl rollout status deployment/anvilops-frontend -n anvilops --timeout=300s

    log_success "Kustomize overlays applied for ${env}."
}

run_smoke_tests() {
    log_step "Running smoke tests..."

    local smoke_test="${SCRIPT_DIR}/smoke-test.sh"
    if [[ -x "$smoke_test" ]]; then
        "$smoke_test"
    else
        log_warn "Smoke test script not found. Performing basic health check..."
        kubectl get pods -n anvilops
        echo ""
        kubectl get svc -n anvilops
    fi
}

main() {
    local env="${1:-}"

    if [[ -z "$env" ]]; then usage; fi

    case "$env" in
        dev|staging|production) ;;
        -h|--help) usage ;;
        *) log_error "Invalid environment: ${env}"; usage ;;
    esac

    if [[ "$env" == "production" ]]; then
        echo ""
        log_warn "You are about to bootstrap the PRODUCTION environment."
        read -rp "Type 'production' to confirm: " confirm
        if [[ "$confirm" != "production" ]]; then
            log_error "Aborted."
            exit 1
        fi
    fi

    echo ""
    log_info "=========================================="
    log_info "  AnvilOps Platform Bootstrap"
    log_info "  Environment: ${env}"
    log_info "=========================================="
    echo ""

    check_prerequisites
    echo ""
    init_state_backend
    echo ""
    run_terraform "$env"
    echo ""
    update_kubeconfig "$env"
    echo ""
    install_helm_charts "$env"
    echo ""
    apply_kustomize "$env"
    echo ""
    run_smoke_tests
    echo ""

    log_success "=========================================="
    log_success "  Bootstrap complete for ${env}!"
    log_success "=========================================="
}

main "$@"
