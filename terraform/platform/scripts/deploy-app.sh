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
    exit 1
}

ENV=""
IMAGE_TAG=""
SKIP_BUILD=false
API_ONLY=false
FRONTEND_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        dev|staging|production) ENV="$1"; shift ;;
        --tag)       IMAGE_TAG="$2"; shift 2 ;;
        --skip-build) SKIP_BUILD=true; shift ;;
        --api-only)  API_ONLY=true; shift ;;
        --frontend-only) FRONTEND_ONLY=true; shift ;;
        -h|--help)   usage ;;
        *)           log_error "Unknown argument: $1"; usage ;;
    esac
done

if [[ -z "$ENV" ]]; then
    log_error "Environment is required."
    usage
fi

if [[ -z "$IMAGE_TAG" ]]; then
    IMAGE_TAG=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "latest")
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

build_and_push() {
    log_step "Building and pushing Docker images (tag: ${IMAGE_TAG})..."

    if [[ "$FRONTEND_ONLY" != "true" ]]; then
        log_info "Building API image..."
        docker build -t "${API_IMAGE}:${IMAGE_TAG}" -t "${API_IMAGE}:latest" \
            -f "${PROJECT_ROOT}/backend/Dockerfile" "${PROJECT_ROOT}/backend"
        docker push "${API_IMAGE}:${IMAGE_TAG}"
        docker push "${API_IMAGE}:latest"
        log_success "API image pushed: ${API_IMAGE}:${IMAGE_TAG}"
    fi

    if [[ "$API_ONLY" != "true" ]]; then
        local frontend_dir="${PROJECT_ROOT}/frontend"
        if [[ -d "$frontend_dir" ]] && [[ -f "${frontend_dir}/Dockerfile" ]]; then
            log_info "Building frontend image..."
            docker build -t "${FRONTEND_IMAGE}:${IMAGE_TAG}" -t "${FRONTEND_IMAGE}:latest" \
                -f "${frontend_dir}/Dockerfile" "$frontend_dir"
            docker push "${FRONTEND_IMAGE}:${IMAGE_TAG}"
            docker push "${FRONTEND_IMAGE}:latest"
            log_success "Frontend image pushed: ${FRONTEND_IMAGE}:${IMAGE_TAG}"
        else
            log_warn "Frontend Dockerfile not found. Skipping frontend build."
        fi
    fi
}

update_kustomize_images() {
    log_step "Updating Kustomize image tags..."
    local overlay_dir="${K8S_DIR}/overlays/${ENV}"
    pushd "$overlay_dir" >/dev/null

    if [[ "$FRONTEND_ONLY" != "true" ]]; then
        kustomize edit set image "anvilops-api:latest=${API_IMAGE}:${IMAGE_TAG}"
    fi
    if [[ "$API_ONLY" != "true" ]]; then
        kustomize edit set image "anvilops-frontend:latest=${FRONTEND_IMAGE}:${IMAGE_TAG}"
    fi

    popd >/dev/null
    log_success "Kustomize image tags updated."
}

apply_manifests() {
    log_step "Applying Kustomize manifests for ${ENV}..."
    local overlay_dir="${K8S_DIR}/overlays/${ENV}"

    kustomize build "$overlay_dir" | kubectl apply --dry-run=server -f -
    kustomize build "$overlay_dir" | kubectl apply -f -
    log_success "Manifests applied."
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

    if [[ "$ENV" == "production" ]]; then
        log_warn "Deploying to PRODUCTION."
        read -rp "Type 'deploy' to confirm: " confirm
        if [[ "$confirm" != "deploy" ]]; then
            log_error "Aborted."
            exit 1
        fi
    fi

    if [[ "$SKIP_BUILD" != "true" ]]; then
        ecr_login
        build_and_push
    fi

    echo ""
    update_kustomize_images
    echo ""
    apply_manifests
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
