#Requires -Version 5.1
<#
.SYNOPSIS
    AnvilOps Smoke Test Script (PowerShell)

.DESCRIPTION
    Validates that the AnvilOps platform is healthy after deployment.

.PARAMETER Endpoint
    Optional external base URL to test (e.g., https://anvilops.devopsnexus.io).

.PARAMETER Namespace
    Kubernetes namespace. Defaults to "anvilops".

.EXAMPLE
    .\smoke-test.ps1
    .\smoke-test.ps1 -Endpoint https://anvilops.devopsnexus.io
#>

[CmdletBinding()]
param(
    [string]$Endpoint,
    [string]$Namespace = "anvilops"
)

$ErrorActionPreference = "Continue"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
function Write-Info { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Blue }
function Write-Pass { param([string]$Msg) Write-Host "[PASS]  $Msg" -ForegroundColor Green }
function Write-Fail { param([string]$Msg) Write-Host "[FAIL]  $Msg" -ForegroundColor Red }
function Write-Step { param([string]$Msg) Write-Host "[TEST]  $Msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
$script:Total  = 0
$script:Passed = 0
$script:Failed = 0

function Record-Pass { param([string]$Msg) $script:Total++; $script:Passed++; Write-Pass $Msg }
function Record-Fail { param([string]$Msg) $script:Total++; $script:Failed++; Write-Fail $Msg }

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
function Test-ApiHealth {
    Write-Step "API health endpoint..."
    try {
        $pod = kubectl get pods -n $Namespace -l app.kubernetes.io/name=anvilops-api `
            -o jsonpath='{.items[0].metadata.name}' 2>$null
    } catch { $pod = "" }

    if (-not $pod) { Record-Fail "API health - no pod found"; return }

    try {
        $response = kubectl exec -n $Namespace $pod -- `
            curl -sf -m 10 http://localhost:8000/api/v1/health 2>$null
    } catch { $response = "TIMEOUT" }

    if ($response -match '"status"') {
        Record-Pass "API health: $response"
    } else {
        Record-Fail "API health: $response"
    }
}

function Test-Frontend {
    Write-Step "Frontend reachability..."
    try {
        $pod = kubectl get pods -n $Namespace -l app.kubernetes.io/name=anvilops-frontend `
            -o jsonpath='{.items[0].metadata.name}' 2>$null
    } catch { $pod = "" }

    if (-not $pod) { Record-Fail "Frontend - no pod found"; return }

    try {
        $code = kubectl exec -n $Namespace $pod -- `
            curl -sf -m 10 -o /dev/null -w '%{http_code}' http://localhost:3000/ 2>$null
    } catch { $code = "000" }

    if ($code -eq "200") {
        Record-Pass "Frontend reachable: HTTP $code"
    } else {
        Record-Fail "Frontend unreachable: HTTP $code"
    }
}

function Test-Redis {
    Write-Step "Redis connectivity via Celery..."
    try {
        $pod = kubectl get pods -n $Namespace -l app.kubernetes.io/name=anvilops-worker `
            -o jsonpath='{.items[0].metadata.name}' 2>$null
    } catch { $pod = "" }

    if (-not $pod) { Record-Fail "Redis - no worker pod"; return }

    try {
        $result = kubectl exec -n $Namespace $pod -- `
            celery -A app.worker.celery_app inspect ping --timeout 10 2>$null
    } catch { $result = "ERROR" }

    if ($result -match "pong") {
        Record-Pass "Redis connectivity via Celery ping"
    } else {
        Record-Fail "Redis connectivity: $result"
    }
}

function Test-PodHealth {
    Write-Step "Pod health summary..."
    $allPods = kubectl get pods -n $Namespace --no-headers 2>$null
    $total   = ($allPods | Measure-Object -Line).Lines
    $notRunning = kubectl get pods -n $Namespace --field-selector=status.phase!=Running `
        --no-headers 2>$null
    $notRunningCount = ($notRunning | Measure-Object -Line).Lines

    if ($notRunningCount -eq 0 -and $total -gt 0) {
        Record-Pass "All $total pods running"
    } elseif ($total -eq 0) {
        Record-Fail "No pods found in namespace $Namespace"
    } else {
        Record-Fail "$notRunningCount of $total pods not running"
    }
}

function Test-External {
    if (-not $Endpoint) { return }
    Write-Step "External endpoint: $Endpoint..."

    try {
        $health = Invoke-RestMethod -Uri "$Endpoint/api/v1/health" -TimeoutSec 15 -ErrorAction Stop
        Record-Pass "External API health: $($health | ConvertTo-Json -Compress)"
    } catch {
        Record-Fail "External API health: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
function Write-Report {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Smoke Test Results"
    Write-Host "=========================================="
    Write-Host "  Total:  $script:Total"
    Write-Host "  Passed: $script:Passed" -ForegroundColor Green
    if ($script:Failed -gt 0) {
        Write-Host "  Failed: $script:Failed" -ForegroundColor Red
    } else {
        Write-Host "  Failed: $script:Failed"
    }
    Write-Host "=========================================="
    if ($script:Failed -eq 0) {
        Write-Host "  All smoke tests passed." -ForegroundColor Green
    } else {
        Write-Host "  $script:Failed test(s) failed." -ForegroundColor Red
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Host ""
Write-Info "AnvilOps Smoke Tests (namespace: $Namespace)"
Write-Host ""

Test-ApiHealth;  Write-Host ""
Test-Frontend;   Write-Host ""
Test-Redis;      Write-Host ""
Test-PodHealth;  Write-Host ""
Test-External

Write-Report

if ($script:Failed -gt 0) { exit 1 }
