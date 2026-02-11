#Requires -Version 5.1
<#
.SYNOPSIS
    AnvilOps Application Deployment Script (PowerShell)

.DESCRIPTION
    Builds Docker images, pushes to ECR, updates Kustomize image tags,
    applies overlays, and verifies rollout health.

.PARAMETER Environment
    Target environment: dev, staging, or production.

.PARAMETER Tag
    Docker image tag. Defaults to the current git short SHA.

.PARAMETER SkipBuild
    Skip Docker build, only update K8s manifests and deploy.

.PARAMETER ApiOnly
    Deploy only the API and worker components.

.PARAMETER FrontendOnly
    Deploy only the frontend component.

.EXAMPLE
    .\deploy-app.ps1 dev
    .\deploy-app.ps1 production -Tag v1.2.3
    .\deploy-app.ps1 dev -SkipBuild
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateSet("dev", "staging", "production")]
    [string]$Environment,

    [string]$Tag,

    [switch]$SkipBuild,
    [switch]$ApiOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PlatformDir = Split-Path -Parent $ScriptDir
$K8sDir      = Join-Path $PlatformDir "k8s"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PlatformDir)

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
function Write-Info    { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Blue }
function Write-Ok      { param([string]$Msg) Write-Host "[OK]    $Msg" -ForegroundColor Green }
function Write-Warn    { param([string]$Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err     { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red }
function Write-Step    { param([string]$Msg) Write-Host "[STEP]  $Msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
# Resolve image tag
# ---------------------------------------------------------------------------
if (-not $Tag) {
    try {
        $Tag = (git -C $ProjectRoot rev-parse --short HEAD 2>$null)
    } catch {
        $Tag = "latest"
    }
    if (-not $Tag) { $Tag = "latest" }
}

# ---------------------------------------------------------------------------
# AWS / ECR settings
# ---------------------------------------------------------------------------
$AccountId  = (aws sts get-caller-identity --query Account --output text)
$Region     = (aws configure get region 2>$null)
if (-not $Region) { $Region = "us-east-1" }

$EcrRegistry   = "${AccountId}.dkr.ecr.${Region}.amazonaws.com"
$ApiImage      = "${EcrRegistry}/anvilops-api"
$FrontendImage = "${EcrRegistry}/anvilops-frontend"

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
function Invoke-EcrLogin {
    Write-Step "Authenticating to ECR..."
    $password = aws ecr get-login-password --region $Region
    $password | docker login --username AWS --password-stdin $EcrRegistry
    if ($LASTEXITCODE -ne 0) { throw "ECR login failed." }
    Write-Ok "ECR login successful."
}

function Invoke-BuildAndPush {
    Write-Step "Building and pushing Docker images (tag: $Tag)..."

    if (-not $FrontendOnly) {
        Write-Info "Building API image..."
        docker build -t "${ApiImage}:${Tag}" -t "${ApiImage}:latest" `
            -f (Join-Path $ProjectRoot "backend/Dockerfile") (Join-Path $ProjectRoot "backend")
        if ($LASTEXITCODE -ne 0) { throw "API image build failed." }
        docker push "${ApiImage}:${Tag}"
        docker push "${ApiImage}:latest"
        Write-Ok "API image pushed: ${ApiImage}:${Tag}"
    }

    if (-not $ApiOnly) {
        $frontendDir = Join-Path $ProjectRoot "frontend"
        $dockerfile  = Join-Path $frontendDir "Dockerfile"
        if ((Test-Path $frontendDir) -and (Test-Path $dockerfile)) {
            Write-Info "Building frontend image..."
            docker build -t "${FrontendImage}:${Tag}" -t "${FrontendImage}:latest" `
                -f $dockerfile $frontendDir
            if ($LASTEXITCODE -ne 0) { throw "Frontend image build failed." }
            docker push "${FrontendImage}:${Tag}"
            docker push "${FrontendImage}:latest"
            Write-Ok "Frontend image pushed: ${FrontendImage}:${Tag}"
        } else {
            Write-Warn "Frontend Dockerfile not found. Skipping frontend build."
        }
    }
}

function Set-KustomizeImage {
    param([string]$Dir, [string]$OldImage, [string]$NewImage)

    $hasKustomize = Get-Command kustomize -ErrorAction SilentlyContinue
    if ($hasKustomize) {
        Push-Location $Dir
        try { kustomize edit set image "${OldImage}=${NewImage}" }
        finally { Pop-Location }
    } else {
        # Fallback: update or add image override in kustomization.yaml
        $kfile   = Join-Path $Dir "kustomization.yaml"
        $name    = ($OldImage -split ":")[0]
        $newName = ($NewImage -split ":")[0]
        $newTag  = ($NewImage -split ":")[-1]
        $content = Get-Content $kfile -Raw

        if ($content -match "(?m)^images:" -and $content -match "name: $([regex]::Escape($name))") {
            # Replace existing entry
            $lines   = Get-Content $kfile
            $output  = @()
            $skip    = $false
            foreach ($line in $lines) {
                if ($line -match "^\s+- name: $([regex]::Escape($name))\s*$") {
                    $output += "  - name: $name"
                    $skip = $true
                    continue
                }
                if ($skip -and $line -match "^\s+newName:") {
                    $output += "    newName: $newName"
                    continue
                }
                if ($skip -and $line -match "^\s+newTag:") {
                    $output += "    newTag: `"$newTag`""
                    $skip = $false
                    continue
                }
                $output += $line
            }
            $output | Set-Content $kfile -Encoding UTF8
        } else {
            # Append new entry
            if ($content -notmatch "(?m)^images:") {
                Add-Content $kfile "`nimages:"
            }
            Add-Content $kfile "  - name: $name`n    newName: $newName`n    newTag: `"$newTag`""
        }
    }
}

function Update-KustomizeImages {
    Write-Step "Updating Kustomize image tags..."
    $overlayDir = Join-Path $K8sDir "overlays/$Environment"

    if (-not $FrontendOnly) {
        Set-KustomizeImage -Dir $overlayDir -OldImage "anvilops-api:latest" -NewImage "${ApiImage}:${Tag}"
    }
    if (-not $ApiOnly) {
        Set-KustomizeImage -Dir $overlayDir -OldImage "anvilops-frontend:latest" -NewImage "${FrontendImage}:${Tag}"
    }

    Write-Ok "Kustomize image tags updated."
}

function Invoke-ApplyManifests {
    Write-Step "Applying Kustomize manifests for $Environment..."
    $overlayDir = Join-Path $K8sDir "overlays/$Environment"

    # Create namespace if it doesn't exist
    kubectl get namespace anvilops 2>$null
    if ($LASTEXITCODE -ne 0) {
        kubectl create namespace anvilops
        Write-Info "Created namespace: anvilops"
    }

    kubectl kustomize $overlayDir | kubectl apply -f -
    if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed." }

    Write-Ok "Manifests applied."
}

function Wait-ForRollout {
    Write-Step "Waiting for rollout completion..."
    $timeout = "300s"
    $failed  = 0

    if (-not $FrontendOnly) {
        kubectl rollout status deployment/anvilops-api -n anvilops --timeout=$timeout
        if ($LASTEXITCODE -ne 0) { $failed++ }
        kubectl rollout status deployment/anvilops-worker -n anvilops --timeout=$timeout
        if ($LASTEXITCODE -ne 0) { $failed++ }
        kubectl rollout status deployment/anvilops-beat -n anvilops --timeout=$timeout
        if ($LASTEXITCODE -ne 0) { $failed++ }
    }

    if (-not $ApiOnly) {
        kubectl rollout status deployment/anvilops-frontend -n anvilops --timeout=$timeout
        if ($LASTEXITCODE -ne 0) { $failed++ }
    }

    if ($failed -gt 0) {
        Write-Err "$failed deployment(s) failed rollout."
        kubectl get pods -n anvilops -o wide
        exit 1
    }

    Write-Ok "All deployments rolled out successfully."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Host ""
Write-Info "=========================================="
Write-Info "  AnvilOps Application Deployment"
Write-Info "  Environment: $Environment"
Write-Info "  Image Tag:   $Tag"
Write-Info "=========================================="
Write-Host ""

if ($Environment -eq "production") {
    Write-Warn "Deploying to PRODUCTION."
    $confirm = Read-Host "Type 'deploy' to confirm"
    if ($confirm -ne "deploy") {
        Write-Err "Aborted."
        exit 1
    }
}

if (-not $SkipBuild) {
    Invoke-EcrLogin
    Invoke-BuildAndPush
}

Write-Host ""
Update-KustomizeImages
Write-Host ""
Invoke-ApplyManifests
Write-Host ""
Wait-ForRollout

Write-Host ""
Write-Ok "=========================================="
Write-Ok "  Deployment complete!"
Write-Ok "  Environment: $Environment"
Write-Ok "  Image Tag:   $Tag"
Write-Ok "=========================================="
