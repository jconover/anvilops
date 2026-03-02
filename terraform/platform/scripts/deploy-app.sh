#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# AnvilOps Application Deployment Script
#
# Builds Docker images, pushes to ECR, updates Kustomize image tags,
# applies overlays, and verifies rollout health.
#
# Usage: ./deploy-app.sh <environment> [--tag <image-tag>] [--skip-build]
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
K8S_DIR="${PLATFORM_DIR}/k8s"
PROJECT_ROOT="$(cd "${PLATFORM_DIR}/../.." && pwd)"

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
    echo "  --tag TAG         Docker image tag (default: git SHA)"
    echo "  --skip-build      Skip Docker build, only update K8s manifests"
    echo "  --api-only        Deploy only the API and worker components"
    echo "  --frontend-only   Deploy only the frontend component"
    echo "  --force           Skip interactive confirmations (for CI/CD)"
    exit 1
}

ENV=""
IMAGE_TAG=""
SKIP_BUILD=false
API_ONLY=false
FRONTEND_ONLY=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        dev|staging|production) ENV="$1"; shift ;;
        --tag)       IMAGE_TAG="$2"; shift 2 ;;
        --skip-build) SKIP_BUILD=true; shift ;;
        --api-only)  API_ONLY=true; shift ;;
        --frontend-only) FRONTEND_ONLY=true; shift ;;
        --force)     FORCE=true; shift ;;
        -h|--help)   usage ;;
        *)           log_error "Unknown argument: $1"; usage ;;
    esac
done

if [[ -z "$ENV" ]]; then
    log_error "Environment is required."
    usage
fi

if [[ -z "$IMAGE_TAG" ]]; then
    IMAGE_TAG=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null) || {
        log_error "Cannot determine git SHA for image tag. Use --tag to specify an image tag."
        exit 1
    }
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
API_IMAGE="${ECR_REGISTRY}/anvilops-api"
FRONTEND_IMAGE="${ECR_REGISTRY}/anvilops-frontend"

ecr_login() {
    log_step "Authenticating to ECR..."
    aws ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "$ECR_REGISTRY"
    log_success "ECR login successful."
}

check_helm_prerequisites() {
    log_step "Checking cluster prerequisites..."
    local missing=0

    # Check External Secrets Operator CRDs (v1 API required)
    if ! kubectl get crd externalsecrets.external-secrets.io &>/dev/null; then
        log_error "External Secrets Operator CRDs not found."
        log_error "Run Step 6 from AWS_AUTOMATED_DEPLOYMENT.md first, or use:"
        log_error "  helm install external-secrets external-secrets/external-secrets \\"
        log_error "    -n external-secrets --create-namespace --set installCRDs=true --wait"
        missing=$((missing + 1))
    elif ! kubectl api-resources --api-group=external-secrets.io 2>/dev/null | grep -q "v1"; then
        log_error "External Secrets Operator installed but v1 API not available."
        log_error "Upgrade to external-secrets >= 0.10:"
        log_error "  helm upgrade external-secrets external-secrets/external-secrets \\"
        log_error "    -n external-secrets --set installCRDs=true --wait"
        missing=$((missing + 1))
    fi

    # Check AWS Load Balancer Controller (needed for Ingress)
    if ! kubectl get deployment aws-load-balancer-controller -n kube-system &>/dev/null; then
        log_warn "AWS Load Balancer Controller not found. Ingress may not work."
    fi

    # Check metrics-server (needed for HPA)
    if ! kubectl get deployment metrics-server -n kube-system &>/dev/null; then
        log_warn "metrics-server not found. HPA will not function."
    fi

    if [[ $missing -gt 0 ]]; then
        log_error "$missing required prerequisite(s) missing. Aborting."
        exit 1
    fi

    log_success "Cluster prerequisites verified."
}

build_and_push() {
    log_step "Building and pushing Docker images (tag: ${IMAGE_TAG})..."

    if [[ "$FRONTEND_ONLY" != "true" ]]; then
        log_info "Building API image..."
        docker build -t "${API_IMAGE}:${IMAGE_TAG}" \
            -f "${PROJECT_ROOT}/backend/Dockerfile" "${PROJECT_ROOT}/backend"
        docker push "${API_IMAGE}:${IMAGE_TAG}"
        log_success "API image pushed: ${API_IMAGE}:${IMAGE_TAG}"
    fi

    if [[ "$API_ONLY" != "true" ]]; then
        local frontend_dir="${PROJECT_ROOT}/frontend"
        if [[ -d "$frontend_dir" ]] && [[ -f "${frontend_dir}/Dockerfile" ]]; then
            log_info "Building frontend image..."
            docker build -t "${FRONTEND_IMAGE}:${IMAGE_TAG}" \
                -f "${frontend_dir}/Dockerfile" "$frontend_dir"
            docker push "${FRONTEND_IMAGE}:${IMAGE_TAG}"
            log_success "Frontend image pushed: ${FRONTEND_IMAGE}:${IMAGE_TAG}"
        else
            log_warn "Frontend Dockerfile not found. Skipping frontend build."
        fi
    fi
}

set_kustomize_image() {
    local dir="$1" old_image="$2" new_image="$3"
    local img_name="${old_image%%:*}"
    local new_name="${new_image%%:*}"
    local new_tag="${new_image##*:}"

    if command -v kustomize &>/dev/null; then
        (cd "$dir" && kustomize edit set image "${img_name}=${new_image}")
    else
        # Fallback: update or add image override in kustomization.yaml
        local kfile="${dir}/kustomization.yaml"
        local tmp="${kfile}.tmp"

        if grep -q "^images:" "$kfile" 2>/dev/null && grep -q "name: ${img_name}$" "$kfile" 2>/dev/null; then
            # Replace existing entry using awk
            awk -v name="$img_name" -v newName="$new_name" -v newTag="$new_tag" '
                /^- name: / { if ($NF == name) { found=1; print "- name: " name; next } else { found=0 } }
                found && /newName:/ { print "  newName: " newName; next }
                found && /newTag:/ { print "  newTag: \"" newTag "\""; found=0; next }
                { print }
            ' "$kfile" > "$tmp" && mv "$tmp" "$kfile"
        else
            # Append new entry
            if ! grep -q "^images:" "$kfile" 2>/dev/null; then
                printf '\nimages:\n' >> "$kfile"
            fi
            printf '  - name: %s\n    newName: %s\n    newTag: "%s"\n' \
                "$img_name" "$new_name" "$new_tag" >> "$kfile"
        fi
    fi
}

update_kustomize_images() {
    log_step "Updating Kustomize image tags..."
    local overlay_dir="${K8S_DIR}/overlays/${ENV}"

    if [[ "$FRONTEND_ONLY" != "true" ]]; then
        set_kustomize_image "$overlay_dir" "anvilops-api" "${API_IMAGE}:${IMAGE_TAG}"
    fi
    if [[ "$API_ONLY" != "true" ]]; then
        set_kustomize_image "$overlay_dir" "anvilops-frontend" "${FRONTEND_IMAGE}:${IMAGE_TAG}"
    fi

    log_success "Kustomize image tags updated."
}

apply_manifests() {
    log_step "Applying Kustomize manifests for ${ENV}..."
    local overlay_dir="${K8S_DIR}/overlays/${ENV}"

    # Create namespace if it doesn't exist
    if ! kubectl get namespace anvilops &>/dev/null; then
        kubectl create namespace anvilops
        log_info "Created namespace: anvilops"
    fi

    kubectl kustomize "$overlay_dir" | kubectl apply -f -
    log_success "Manifests applied."
}

patch_service_accounts() {
    log_step "Patching IRSA annotations on service accounts..."
    kubectl annotate serviceaccount anvilops-api -n anvilops \
        "eks.amazonaws.com/role-arn=arn:aws:iam::${ACCOUNT_ID}:role/anvilops-api-${ENV}" \
        --overwrite
    log_success "Annotated anvilops-api with IRSA role: anvilops-api-${ENV}"

    kubectl annotate serviceaccount anvilops-worker -n anvilops \
        "eks.amazonaws.com/role-arn=arn:aws:iam::${ACCOUNT_ID}:role/anvilops-worker-${ENV}" \
        --overwrite
    log_success "Annotated anvilops-worker with IRSA role: anvilops-worker-${ENV}"
}

wait_for_rollout() {
    log_step "Waiting for rollout completion..."
    local timeout="300s"
    local failed=0

    if [[ "$FRONTEND_ONLY" != "true" ]]; then
        kubectl rollout status deployment/anvilops-api -n anvilops --timeout="$timeout" || failed=$((failed + 1))
        kubectl rollout status deployment/anvilops-worker -n anvilops --timeout="$timeout" || failed=$((failed + 1))
        kubectl rollout status deployment/anvilops-beat -n anvilops --timeout="$timeout" || failed=$((failed + 1))
    fi

    if [[ "$API_ONLY" != "true" ]]; then
        kubectl rollout status deployment/anvilops-frontend -n anvilops --timeout="$timeout" || failed=$((failed + 1))
    fi

    if [[ $failed -gt 0 ]]; then
        log_error "${failed} deployment(s) failed rollout."
        kubectl get pods -n anvilops -o wide
        exit 1
    fi

    log_success "All deployments rolled out successfully."
}

main() {
    echo ""
    log_info "=========================================="
    log_info "  AnvilOps Application Deployment"
    log_info "  Environment: ${ENV}"
    log_info "  Image Tag:   ${IMAGE_TAG}"
    log_info "=========================================="
    echo ""

    if [[ "$ENV" == "production" ]] && [[ "$FORCE" != "true" ]]; then
        log_warn "Deploying to PRODUCTION."
        read -rp "Type 'deploy' to confirm: " confirm
        if [[ "$confirm" != "deploy" ]]; then
            log_error "Aborted."
            exit 1
        fi
    fi

    check_helm_prerequisites

    if [[ "$SKIP_BUILD" != "true" ]]; then
        ecr_login
        build_and_push
    fi

    echo ""
    update_kustomize_images
    echo ""
    apply_manifests
    echo ""
    patch_service_accounts
    echo ""
    wait_for_rollout

    echo ""
    log_success "=========================================="
    log_success "  Deployment complete!"
    log_success "  Environment: ${ENV}"
    log_success "  Image Tag:   ${IMAGE_TAG}"
    log_success "=========================================="
}

main
