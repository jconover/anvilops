#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# AnvilOps Environment Park / Unpark Script
#
# Stops or starts billable resources without destroying infrastructure.
# Use this when you're testing for a few hours and want to avoid idle costs.
#
# Usage:
#   ./park.sh <environment>            # Park (stop/scale down)
#   ./park.sh <environment> --start    # Unpark (start/scale up)
#   ./park.sh <environment> --status   # Show current state of resources
#
# What gets parked:
#   - EKS node group      -> scaled to 0 nodes
#   - RDS PostgreSQL       -> stopped (auto-restarts after 7 days)
#   - Puppet Enterprise    -> EC2 instance stopped
#
# What keeps running (can't be stopped without destroy):
#   - EKS control plane    ~$0.10/hr
#   - NAT Gateway          ~$0.045/hr
#   - ALB                  ~$0.023/hr
#   - ElastiCache Redis    ~$0.017/hr
#   Idle total: ~$0.19/hr (~$4.50/day)
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

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

ENV=""
ACTION="park"

usage() {
    echo "Usage: $(basename "$0") <environment> [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --start    Unpark: start resources and scale up"
    echo "  --status   Show current state of resources"
    echo "  (default)  Park: stop resources and scale to zero"
    echo ""
    echo "Environments: dev, staging"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        dev|staging) ENV="$1"; shift ;;
        --start)     ACTION="unpark"; shift ;;
        --status)    ACTION="status"; shift ;;
        -h|--help)   usage ;;
        production)  log_error "Refusing to park production."; exit 1 ;;
        *)           log_error "Unknown argument: $1"; usage ;;
    esac
done

if [[ -z "$ENV" ]]; then log_error "Environment is required."; usage; fi

PROJECT="anvilops"
CLUSTER_NAME="${PROJECT}-${ENV}"
NODEGROUP_NAME="${CLUSTER_NAME}-workers"
RDS_IDENTIFIER="${PROJECT}-${ENV}"
PUPPET_TAG="puppet-${ENV}"
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

# -----------------------------------------------------------------------------
# Status
# -----------------------------------------------------------------------------

get_nodegroup_status() {
    aws eks describe-nodegroup \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODEGROUP_NAME" \
        --region "$REGION" \
        --query '{status: nodegroup.status, desired: nodegroup.scalingConfig.desiredSize, min: nodegroup.scalingConfig.minSize, max: nodegroup.scalingConfig.maxSize}' \
        --output json 2>/dev/null || echo '{"error": "not found"}'
}

get_rds_status() {
    aws rds describe-db-instances \
        --db-instance-identifier "$RDS_IDENTIFIER" \
        --region "$REGION" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text 2>/dev/null || echo "not-found"
}

get_puppet_instance() {
    aws ec2 describe-instances \
        --region "$REGION" \
        --filters "Name=tag:Name,Values=${PUPPET_TAG}" "Name=instance-state-name,Values=running,stopped,stopping,pending" \
        --query 'Reservations[0].Instances[0].[InstanceId, State.Name]' \
        --output text 2>/dev/null || echo "not-found"
}

show_status() {
    log_step "Resource status for ${ENV}..."
    echo ""

    log_info "EKS Node Group (${NODEGROUP_NAME}):"
    local ng_info
    ng_info=$(get_nodegroup_status)
    echo "  $ng_info"
    echo ""

    log_info "RDS (${RDS_IDENTIFIER}):"
    local rds_status
    rds_status=$(get_rds_status)
    echo "  Status: $rds_status"
    echo ""

    log_info "Puppet EC2 (${PUPPET_TAG}):"
    local puppet_info
    puppet_info=$(get_puppet_instance)
    echo "  $puppet_info"
}

# -----------------------------------------------------------------------------
# Park (stop/scale down)
# -----------------------------------------------------------------------------

park_eks_nodes() {
    log_step "Scaling EKS node group to 0..."

    aws eks update-nodegroup-config \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODEGROUP_NAME" \
        --region "$REGION" \
        --scaling-config minSize=0,desiredSize=0 \
        --query 'update.status' \
        --output text

    log_success "Node group scaling to 0 (nodes will drain over ~5 min)."
}

park_rds() {
    log_step "Stopping RDS instance..."

    local status
    status=$(get_rds_status)

    if [[ "$status" == "stopped" ]]; then
        log_warn "RDS already stopped."
        return 0
    fi

    if [[ "$status" != "available" ]]; then
        log_warn "RDS is in state '${status}', cannot stop. Skipping."
        return 0
    fi

    aws rds stop-db-instance \
        --db-instance-identifier "$RDS_IDENTIFIER" \
        --region "$REGION" \
        --query 'DBInstance.DBInstanceStatus' \
        --output text

    log_success "RDS stopping (takes ~5 min). Note: auto-restarts after 7 days."
}

park_puppet() {
    log_step "Stopping Puppet EC2 instance..."

    local puppet_info instance_id state
    puppet_info=$(get_puppet_instance)
    instance_id=$(echo "$puppet_info" | awk '{print $1}')
    state=$(echo "$puppet_info" | awk '{print $2}')

    if [[ "$instance_id" == "not-found" || "$instance_id" == "None" ]]; then
        log_warn "Puppet instance not found. Skipping."
        return 0
    fi

    if [[ "$state" == "stopped" ]]; then
        log_warn "Puppet instance already stopped."
        return 0
    fi

    aws ec2 stop-instances \
        --instance-ids "$instance_id" \
        --region "$REGION" \
        --query 'StoppingInstances[0].CurrentState.Name' \
        --output text

    log_success "Puppet instance ${instance_id} stopping."
}

# -----------------------------------------------------------------------------
# Unpark (start/scale up)
# -----------------------------------------------------------------------------

unpark_rds() {
    log_step "Starting RDS instance..."

    local status
    status=$(get_rds_status)

    if [[ "$status" == "available" ]]; then
        log_warn "RDS already running."
        return 0
    fi

    if [[ "$status" != "stopped" ]]; then
        log_warn "RDS is in state '${status}', cannot start. Skipping."
        return 0
    fi

    aws rds start-db-instance \
        --db-instance-identifier "$RDS_IDENTIFIER" \
        --region "$REGION" \
        --query 'DBInstance.DBInstanceStatus' \
        --output text

    log_success "RDS starting (takes ~5-10 min)."
}

unpark_puppet() {
    log_step "Starting Puppet EC2 instance..."

    local puppet_info instance_id state
    puppet_info=$(get_puppet_instance)
    instance_id=$(echo "$puppet_info" | awk '{print $1}')
    state=$(echo "$puppet_info" | awk '{print $2}')

    if [[ "$instance_id" == "not-found" || "$instance_id" == "None" ]]; then
        log_warn "Puppet instance not found. Skipping."
        return 0
    fi

    if [[ "$state" == "running" ]]; then
        log_warn "Puppet instance already running."
        return 0
    fi

    aws ec2 start-instances \
        --instance-ids "$instance_id" \
        --region "$REGION" \
        --query 'StartingInstances[0].CurrentState.Name' \
        --output text

    log_success "Puppet instance ${instance_id} starting."
}

unpark_eks_nodes() {
    log_step "Scaling EKS node group back up..."

    # Read desired sizes from tfvars if available
    local tfvars="${PLATFORM_DIR}/terraform.${ENV}.tfvars"
    local min_size=1 desired_size=2 max_size=3

    if [[ -f "$tfvars" ]]; then
        local val
        val=$(grep -oP 'eks_node_min_size\s*=\s*\K\d+' "$tfvars" 2>/dev/null || true)
        [[ -n "$val" ]] && min_size="$val"
        val=$(grep -oP 'eks_node_desired_size\s*=\s*\K\d+' "$tfvars" 2>/dev/null || true)
        [[ -n "$val" ]] && desired_size="$val"
        val=$(grep -oP 'eks_node_max_size\s*=\s*\K\d+' "$tfvars" 2>/dev/null || true)
        [[ -n "$val" ]] && max_size="$val"
    fi

    log_info "Restoring scaling config: min=${min_size}, desired=${desired_size}, max=${max_size}"

    aws eks update-nodegroup-config \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODEGROUP_NAME" \
        --region "$REGION" \
        --scaling-config "minSize=${min_size},desiredSize=${desired_size},maxSize=${max_size}" \
        --query 'update.status' \
        --output text

    log_success "Node group scaling up (nodes ready in ~5 min)."
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    echo ""

    case "$ACTION" in
        status)
            show_status
            ;;
        park)
            log_info "=========================================="
            log_info "  Parking ${ENV} environment"
            log_info "=========================================="
            echo ""
            park_eks_nodes
            echo ""
            park_rds
            echo ""
            park_puppet
            echo ""
            log_success "=========================================="
            log_success "  ${ENV} parked. Idle cost: ~\$0.19/hr"
            log_success "  Unpark with: $(basename "$0") ${ENV} --start"
            log_success "=========================================="
            ;;
        unpark)
            log_info "=========================================="
            log_info "  Unparking ${ENV} environment"
            log_info "=========================================="
            echo ""
            # Start RDS first -- it takes the longest
            unpark_rds
            echo ""
            unpark_puppet
            echo ""
            unpark_eks_nodes
            echo ""
            log_success "=========================================="
            log_success "  ${ENV} unparking. All resources ready in ~10 min."
            log_success "=========================================="
            ;;
    esac
}

main
