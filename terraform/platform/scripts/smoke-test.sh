#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# AnvilOps Smoke Test Script
#
# Validates that the AnvilOps platform is healthy after deployment.
#
# Usage: ./smoke-test.sh [--endpoint <base-url>] [--namespace <ns>]
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
log_step()    { echo -e "${CYAN}[TEST]${NC}  $*"; }

NAMESPACE="anvilops"
BASE_URL=""
TOTAL=0
PASSED=0
FAILED=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --endpoint)  BASE_URL="$2"; shift 2 ;;
        --namespace) NAMESPACE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $(basename "$0") [--endpoint <base-url>] [--namespace <ns>]"
            exit 0
            ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

record_pass() { TOTAL=$((TOTAL + 1)); PASSED=$((PASSED + 1)); log_success "$1"; }
record_fail() { TOTAL=$((TOTAL + 1)); FAILED=$((FAILED + 1)); log_fail "$1"; }

test_api_health() {
    log_step "API health endpoint..."
    local api_pod
    api_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=anvilops-api \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [[ -z "$api_pod" ]]; then record_fail "API health - no pod found"; return; fi

    local response
    response=$(kubectl exec -n "$NAMESPACE" "$api_pod" -- \
        curl -sf -m 10 http://localhost:8000/api/v1/health 2>/dev/null || echo "TIMEOUT")

    if echo "$response" | grep -qi '"status"'; then
        record_pass "API health: ${response}"
    else
        record_fail "API health: ${response}"
    fi
}

test_frontend() {
    log_step "Frontend reachability..."
    local pod
    pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=anvilops-frontend \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [[ -z "$pod" ]]; then record_fail "Frontend - no pod found"; return; fi

    local code
    code=$(kubectl exec -n "$NAMESPACE" "$pod" -- \
        curl -sf -m 10 -o /dev/null -w '%{http_code}' http://localhost:3000/ 2>/dev/null || echo "000")

    if [[ "$code" == "200" ]]; then
        record_pass "Frontend reachable: HTTP ${code}"
    else
        record_fail "Frontend unreachable: HTTP ${code}"
    fi
}

test_redis() {
    log_step "Redis connectivity via Celery..."
    local pod
    pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=anvilops-worker \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

    if [[ -z "$pod" ]]; then record_fail "Redis - no worker pod"; return; fi

    local result
    result=$(kubectl exec -n "$NAMESPACE" "$pod" -- \
        celery -A app.worker.celery_app inspect ping --timeout 10 2>/dev/null || echo "ERROR")

    if echo "$result" | grep -qi "pong"; then
        record_pass "Redis connectivity via Celery ping"
    else
        record_fail "Redis connectivity: ${result}"
    fi
}

test_pod_health() {
    log_step "Pod health summary..."
    local not_running
    not_running=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running \
        --no-headers 2>/dev/null | wc -l)
    local total
    total=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)

    if [[ "$not_running" -eq 0 ]] && [[ "$total" -gt 0 ]]; then
        record_pass "All ${total} pods running"
    elif [[ "$total" -eq 0 ]]; then
        record_fail "No pods found in namespace ${NAMESPACE}"
    else
        record_fail "${not_running} of ${total} pods not running"
    fi
}

test_external() {
    if [[ -z "$BASE_URL" ]]; then return; fi
    log_step "External endpoint: ${BASE_URL}..."

    local health
    health=$(curl -sf -m 15 "${BASE_URL}/api/v1/health" 2>/dev/null || echo "ERROR")
    if echo "$health" | grep -qi '"status"'; then
        record_pass "External API health: ${health}"
    else
        record_fail "External API health: ${health}"
    fi
}

print_report() {
    echo ""
    echo "=========================================="
    echo "  Smoke Test Results"
    echo "=========================================="
    echo -e "  Total:  ${TOTAL}"
    echo -e "  ${GREEN}Passed: ${PASSED}${NC}"
    if [[ $FAILED -gt 0 ]]; then
        echo -e "  ${RED}Failed: ${FAILED}${NC}"
    else
        echo -e "  Failed: ${FAILED}"
    fi
    echo "=========================================="
    if [[ $FAILED -eq 0 ]]; then
        echo -e "${GREEN}  All smoke tests passed.${NC}"
    else
        echo -e "${RED}  ${FAILED} test(s) failed.${NC}"
    fi
}

main() {
    echo ""
    log_info "AnvilOps Smoke Tests (namespace: ${NAMESPACE})"
    echo ""

    test_api_health; echo ""
    test_frontend; echo ""
    test_redis; echo ""
    test_pod_health; echo ""
    test_external

    print_report
    [[ $FAILED -gt 0 ]] && exit 1
}

main
