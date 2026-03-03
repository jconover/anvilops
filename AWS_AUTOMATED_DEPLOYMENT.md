# AnvilOps -- Automated AWS Deployment Guide

Deploy the entire AnvilOps platform to AWS using Terraform. This guide is the automated counterpart to [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md), which provides the manual step-by-step reference for each component. If you want to understand what each resource does and why, read that document first. If you want to deploy everything with minimal effort, follow this one.

> **How these two guides relate:** This automated guide covers the complete infrastructure provisioning and Day-1 configuration (Steps 1–11), including AWX, Puppet Enterprise, CI/CD, and monitoring. The companion [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md) provides manual step-by-step reference if you need to understand what each resource does. You do **not** need to follow any sections of AWS_DEPLOYMENT.md when using this automated guide.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Directory Structure](#3-directory-structure)
4. [Quick Start (TL;DR)](#4-quick-start-tldr)
5. [Step-by-Step Deployment](#5-step-by-step-deployment)
6. [Post-Deployment Configuration](#6-post-deployment-configuration)
   - [6a. AWX Configuration Details](#6a-awx-configuration-details)
   - [6b. Puppet Enterprise Details](#6b-puppet-enterprise-details)
   - [6c. CI/CD Pipeline Setup](#6c-cicd-pipeline-setup)
   - [6d. Monitoring & Observability](#6d-monitoring--observability)
7. [Environment Promotion](#7-environment-promotion)
8. [Updating the Application](#8-updating-the-application)
9. [Scaling Guide](#9-scaling-guide)
10. [Troubleshooting](#10-troubleshooting)
11. [Teardown](#11-teardown)
12. [Cost Optimization Tips](#12-cost-optimization-tips)

---

## 1. Overview

This guide deploys the entire AnvilOps server provisioning platform to AWS using the Terraform code in `terraform/platform/`. A single `terraform apply` creates and wires together every piece of infrastructure the platform needs.

### What Gets Created

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| Networking | VPC, Subnets, NAT Gateways, IGW | Multi-AZ network with public, private, and isolated tiers |
| Compute (Platform) | EKS (Managed Node Groups) | Runs API, frontend, Celery workers, AWX |
| Database | RDS PostgreSQL 16 (Multi-AZ) | Persistent state for server requests, audit logs, approvals |
| Cache / Broker | ElastiCache Redis 7 (2 nodes) | Celery task broker and result backend |
| Auth | Cognito User Pool + App Client | User authentication with RBAC groups |
| Container Registry | ECR (4 repositories) | Stores API, frontend, worker, and Terraform runner images |
| Load Balancer | ALB + WAF v2 | HTTPS ingress with managed security rules |
| DNS | Route 53 (public + private zones) | External access and internal Puppet resolution |
| Monitoring | CloudWatch (logs, metrics, alarms, dashboards) | Observability across all components |
| Terraform Runner | ECS Fargate cluster + task definition | Ephemeral containers for terraform plan/apply |
| Compliance | Puppet Enterprise EC2 (r5.xlarge) | Day-2+ drift detection and enforcement |
| AWX (Ansible) | AWX Operator + AWX CR (EKS) | Ansible automation for server provisioning playbooks |
| Monitoring Stack | kube-prometheus-stack (EKS) | Prometheus metrics, Grafana dashboards, Alertmanager |
| Security | IAM roles, IRSA, Secrets Manager, KMS | Least-privilege access, encrypted secrets |
| State Backend | S3 (native locking) | Terraform state storage and locking |

### Key Numbers

- **Estimated deployment time:** ~45 minutes (EKS alone takes ~15 minutes)
- **Estimated monthly cost:** ~$1,740 (see [AWS_DEPLOYMENT.md, Section 18](./AWS_DEPLOYMENT.md))
- **Regions:** us-east-1 (primary), us-west-2 (secondary)
- **Availability:** Multi-AZ for RDS, ElastiCache, and EKS node groups

---

## 2. Prerequisites

### Required Tools

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| AWS CLI | v2 | AWS API access |
| Terraform | >= 1.9.0 | Infrastructure provisioning |
| kubectl | 1.29+ | Kubernetes cluster management |
| Helm | v3 | Kubernetes package management |
| kustomize | Latest | Kubernetes manifest overlays (optional — kubectl has built-in support) |
| Docker | Latest | Building container images |
| jq | Latest | JSON parsing in scripts |

### AWS Account Requirements

- An AWS account with administrator access
- AWS CLI configured with credentials:

```bash
aws configure
aws sts get-caller-identity
```

### Other Requirements

- A registered domain name you control (for Route 53 and ACM)
- A Git repository containing your Puppet code (for Code Manager)

---

## 3. Directory Structure

```
terraform/platform/
├── main.tf, variables.tf, outputs.tf, providers.tf, backend.tf, versions.tf
├── terraform.tfvars.example
├── modules/
│   ├── networking/          # VPC, subnets, NAT GWs, security groups
│   ├── eks/                 # EKS cluster, managed node groups, OIDC
│   ├── rds/                 # RDS PostgreSQL 16, Multi-AZ
│   ├── elasticache/         # ElastiCache Redis 7, replication group
│   ├── ecr/                 # 4 ECR repositories
│   ├── ecs-runner/          # ECS Fargate for Terraform runner
│   ├── iam/                 # 9 IAM roles (6 IRSA + 3 non-IRSA)
│   ├── cognito/             # Cognito user pool, RBAC groups
│   ├── alb/                 # ALB, ACM, WAF v2, target groups
│   ├── dns/                 # Route 53, health checks
│   ├── monitoring/          # CloudWatch alarms, dashboard, SNS
│   ├── puppet/              # Puppet Enterprise EC2
│   └── state-backend/       # S3 for TF state (native locking)
├── k8s/
│   ├── base/                # Kustomize base manifests
│   └── overlays/
│       ├── dev/
│       ├── staging/
│       └── production/
├── helm/                    # Helm chart values files
└── scripts/
    ├── bootstrap.sh         # Full deployment (bash)
    ├── deploy-app.sh        # App build + deploy (bash)
    ├── deploy-app.ps1       # App build + deploy (PowerShell)
    ├── smoke-test.sh        # Health validation (bash)
    ├── smoke-test.ps1       # Health validation (PowerShell)
    └── destroy.sh           # Teardown (bash)
```

---

## 4. Quick Start (TL;DR)

### Bootstrap the State Backend (one-time)

This creates the S3 bucket that stores Terraform state. Run once per AWS account:

```bash
cd terraform/platform/modules/state-backend
terraform init
terraform apply -var="project_name=anvilops" -var="environment=dev"
# Note the output: state_bucket_name
```

### Initialize and Deploy

**Bash / macOS / Linux:**

```bash
cd terraform/platform
terraform init -backend-config="bucket=<state_bucket_name>" -backend-config="key=platform/terraform.tfstate" -backend-config="region=us-east-1" -backend-config="use_lockfile=true"

# ── Option A: Dev / Demo (~$305/month) ──────────────────────────────
cp terraform.dev.tfvars.example terraform.dev.tfvars
# Edit terraform.dev.tfvars with your domain and zone ID
terraform plan -var-file terraform.dev.tfvars -out tfplan
terraform apply tfplan
aws eks update-kubeconfig --name $(terraform output -raw eks_cluster_name) --region us-east-1

# Install required Helm charts (see Step 6 for details)
helm repo add external-secrets https://charts.external-secrets.io && helm repo update
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --set installCRDs=true --wait
# See Step 6 for additional charts: ALB controller, External DNS, metrics-server, etc.

./scripts/deploy-app.sh dev
./scripts/smoke-test.sh

# ── Option B: Production (~$1,740/month) ────────────────────────────
cp terraform.production.tfvars.example terraform.production.tfvars
# Edit terraform.production.tfvars with your domain and zone ID
terraform plan -var-file terraform.production.tfvars -out tfplan
terraform apply tfplan
aws eks update-kubeconfig --name $(terraform output -raw eks_cluster_name) --region us-east-1

# Install required Helm charts (see Step 6 for details)
helm repo add external-secrets https://charts.external-secrets.io && helm repo update
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --set installCRDs=true --wait
# See Step 6 for additional charts: ALB controller, External DNS, metrics-server, etc.

./scripts/deploy-app.sh production
./scripts/smoke-test.sh

# ── Option C: Custom ────────────────────────────────────────────────
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform plan -out tfplan
terraform apply tfplan
```

**PowerShell (Windows):**

```powershell
cd terraform\platform
terraform init -backend-config="bucket=<state_bucket_name>" -backend-config="key=platform/terraform.tfstate" -backend-config="region=us-east-1" -backend-config="use_lockfile=true"

# ── Option A: Dev / Demo (~$305/month) ──────────────────────────────
Copy-Item terraform.dev.tfvars.example terraform.dev.tfvars
# Edit terraform.dev.tfvars with your domain and zone ID
terraform plan -var-file terraform.dev.tfvars -out tfplan
terraform apply tfplan
$ClusterName = terraform output -raw eks_cluster_name
aws eks update-kubeconfig --name $ClusterName --region us-east-1

# Install required Helm charts (see Step 6 for details)
helm repo add external-secrets https://charts.external-secrets.io; helm repo update
helm install external-secrets external-secrets/external-secrets `
  -n external-secrets --create-namespace --set installCRDs=true --wait
# See Step 6 for additional charts: ALB controller, External DNS, metrics-server, etc.

.\scripts\deploy-app.ps1 dev
.\scripts\smoke-test.ps1

# ── Option B: Production (~$1,740/month) ────────────────────────────
Copy-Item terraform.production.tfvars.example terraform.production.tfvars
# Edit terraform.production.tfvars with your domain and zone ID
terraform plan -var-file terraform.production.tfvars -out tfplan
terraform apply tfplan
$ClusterName = terraform output -raw eks_cluster_name
aws eks update-kubeconfig --name $ClusterName --region us-east-1

# Install required Helm charts (see Step 6 for details)
helm repo add external-secrets https://charts.external-secrets.io; helm repo update
helm install external-secrets external-secrets/external-secrets `
  -n external-secrets --create-namespace --set installCRDs=true --wait
# See Step 6 for additional charts: ALB controller, External DNS, metrics-server, etc.

.\scripts\deploy-app.ps1 production
.\scripts\smoke-test.ps1

# ── Option C: Custom ────────────────────────────────────────────────
Copy-Item terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform plan -out tfplan
terraform apply tfplan
```

---

## 5. Step-by-Step Deployment

### Step 1: Configure Variables

Pre-built tfvars files are included for dev and production. Use one directly, or copy the example to customize:

```bash
cd terraform/platform

# Option 1 — Use the dev/demo environment as-is
terraform plan -var-file terraform.dev.tfvars -out tfplan

# Option 2 — Use the production environment as-is
terraform plan -var-file terraform.production.tfvars -out tfplan

# Option 3 — Customize from the example
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars, then:
terraform plan -out tfplan
```

**Environment sizing comparison:**

| Variable | Dev (~$350/mo) | Staging | Production (~$1,740/mo) |
|----------|---------------|---------|------------------------|
| `single_nat_gateway` | true | true | false |
| `eks_node_instance_types` | t3.medium | t3.xlarge | t3.xlarge |
| `eks_node_desired_size` | 2 | 3 | 4 |
| `db_instance_class` | db.t3.small | db.t3.large | db.r6g.large |
| `db_allocated_storage` | 20 GB | 50 GB | 100 GB |
| `redis_node_type` | cache.t3.micro | cache.t3.medium | cache.r6g.large |
| `redis_num_cache_clusters` | 1 | 1 | 2 |
| `puppet_instance_type` | t3.large | r5.xlarge | r5.xlarge |
| `enable_waf` | false | true | true |
| `enable_deletion_protection` | false | false | true |

### Step 2: Bootstrap State Backend

One-time operation per AWS account:

```bash
cd terraform/platform/modules/state-backend
terraform init
terraform apply -var="project_name=anvilops" -var="environment=production"
```

Note the output value (`state_bucket_name`).

### Step 3: Initialize Main Platform

```bash
cd terraform/platform
terraform init -backend-config="bucket=<state_bucket_name>" -backend-config="key=platform/terraform.tfstate" -backend-config="region=us-east-1" -backend-config="use_lockfile=true"
```

### Step 4: Plan and Apply

```bash
terraform plan  -var-file terraform.dev.tfvars -out tfplan
terraform apply tfplan
```

~25-30 minutes. Longest resources: EKS (~15min), RDS (~10min), ElastiCache (~8min).

### Step 5: Configure kubectl

**Bash / macOS / Linux:**

```bash
aws eks update-kubeconfig --name $(terraform output -raw eks_cluster_name) --region us-east-1
kubectl get nodes
```

**PowerShell (Windows):**

```powershell
$ClusterName = terraform output -raw eks_cluster_name
aws eks update-kubeconfig --name $ClusterName --region us-east-1
kubectl get nodes
```

### Step 6: Install Helm Charts

EKS add-ons must be installed before deploying the application. Choose **one** of the two options below:

- **[Option A: Helm CLI](#option-a-helm-cli-quick-setup)** — Quick one-off setup, good for learning or ad-hoc installs.
- **[Option B: Terraform](#option-b-terraform-repeatable-all-environments)** — Repeatable and idempotent. Recommended for all environments (dev, staging, production). Jump to [Option B](#option-b-terraform-repeatable-all-environments) if you prefer infrastructure-as-code.

> **Do not mix Option A and Option B.** Helm releases can only be managed by one tool at a time. If you already ran Option A and want to switch to Terraform, uninstall the manual releases first:
> ```bash
> helm uninstall aws-load-balancer-controller -n kube-system
> helm uninstall external-secrets -n external-secrets
> helm uninstall external-dns -n external-dns
> helm uninstall metrics-server -n kube-system
> helm uninstall cluster-autoscaler -n kube-system
> helm uninstall keda -n keda
> ```
> Then run Option B with a clean slate.

**Option A: Helm CLI (quick setup)**

**Bash / macOS / Linux:**

```bash
# Add repos
helm repo add eks https://aws.github.io/eks-charts
helm repo add external-secrets https://charts.external-secrets.io
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm repo add keda https://kedacore.github.io/charts
helm repo update

# Set variables (update these for your environment)
CLUSTER_NAME=$(terraform output -raw eks_cluster_name)
VPC_ID=$(terraform output -raw vpc_id)
REGION=us-east-1
ALB_ROLE_ARN=$(terraform output -raw alb_controller_role_arn)
EXTDNS_ROLE_ARN=$(terraform output -raw external_dns_role_arn)
AUTOSCALER_ROLE_ARN=$(terraform output -raw cluster_autoscaler_role_arn)
DOMAIN=anvilops.devopsnexus.io

# 1. AWS Load Balancer Controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$ALB_ROLE_ARN --set region=$REGION --set vpcId=$VPC_ID --wait

# 2. External Secrets Operator
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace --wait

# 3. External DNS
helm install external-dns external-dns/external-dns -n external-dns --create-namespace --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$EXTDNS_ROLE_ARN --set provider.name=aws --set "domainFilters[0]=$DOMAIN" --set policy=sync --set registry=txt --set txtOwnerId=$CLUSTER_NAME --wait

# 4. Metrics Server
helm install metrics-server metrics-server/metrics-server -n kube-system --wait

# 5. Cluster Autoscaler
helm install cluster-autoscaler autoscaler/cluster-autoscaler -n kube-system --set autoDiscovery.clusterName=$CLUSTER_NAME --set awsRegion=$REGION --set rbac.serviceAccount.name=cluster-autoscaler --set rbac.serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$AUTOSCALER_ROLE_ARN --wait

# 6. KEDA (Celery worker autoscaling)
helm install keda keda/keda -n keda --create-namespace --wait
```

**PowerShell (Windows):**

```powershell
# Add repos
helm repo add eks https://aws.github.io/eks-charts
helm repo add external-secrets https://charts.external-secrets.io
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm repo add keda https://kedacore.github.io/charts
helm repo update

# Set variables (update these for your environment)
$ClusterName   = terraform output -raw eks_cluster_name
$VpcId         = terraform output -raw vpc_id
$Region        = "us-east-1"
$AlbRoleArn    = terraform output -raw alb_controller_role_arn
$ExtDnsRoleArn = terraform output -raw external_dns_role_arn
$AutoscalerArn = terraform output -raw cluster_autoscaler_role_arn
$Domain        = "anvilops.devopsnexus.io"

# 1. AWS Load Balancer Controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$ClusterName --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$AlbRoleArn --set region=$Region --set vpcId=$VpcId --wait

# 2. External Secrets Operator
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace --wait

# 3. External DNS
helm install external-dns external-dns/external-dns -n external-dns --create-namespace --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$ExtDnsRoleArn --set provider.name=aws --set "domainFilters[0]=$Domain" --set policy=sync --set registry=txt --set txtOwnerId=$ClusterName --wait

# 4. Metrics Server
helm install metrics-server metrics-server/metrics-server -n kube-system --wait

# 5. Cluster Autoscaler
helm install cluster-autoscaler autoscaler/cluster-autoscaler -n kube-system --set autoDiscovery.clusterName=$ClusterName --set awsRegion=$Region --set rbac.serviceAccount.name=cluster-autoscaler --set rbac.serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$AutoscalerArn --wait

# 6. KEDA (Celery worker autoscaling)
helm install keda keda/keda -n keda --create-namespace --wait
```

**Option B: Terraform (repeatable, all environments)**

The Terraform module auto-discovers cluster endpoint, CA certificate, and auth token
from the cluster name — no manual token passing required.

**Bash / macOS / Linux:**

```bash
cd terraform/platform/helm
terraform init

# Set variables from platform outputs (if not already set from Option A above)
CLUSTER_NAME=$(terraform -chdir=.. output -raw eks_cluster_name)
VPC_ID=$(terraform -chdir=.. output -raw vpc_id)
REGION=us-east-1
ALB_ROLE_ARN=$(terraform -chdir=.. output -raw alb_controller_role_arn)
EXTDNS_ROLE_ARN=$(terraform -chdir=.. output -raw external_dns_role_arn)
AUTOSCALER_ROLE_ARN=$(terraform -chdir=.. output -raw cluster_autoscaler_role_arn)
DOMAIN=anvilops.devopsnexus.io

## Change "dev" to "staging" or "production" as needed
terraform apply \
  -var="cluster_name=$CLUSTER_NAME" \
  -var="vpc_id=$VPC_ID" \
  -var="region=$REGION" \
  -var="environment=dev" \
  -var="domain=$DOMAIN" \
  -var="alb_controller_role_arn=$ALB_ROLE_ARN" \
  -var="external_dns_role_arn=$EXTDNS_ROLE_ARN" \
  -var="cluster_autoscaler_role_arn=$AUTOSCALER_ROLE_ARN" \
  -var="redis_endpoint=placeholder"
```

**PowerShell (Windows):**

```powershell
cd terraform\platform\helm
terraform init

# Set variables from platform outputs (if not already set from Option A above)
$ClusterName   = terraform "-chdir=.." output -raw eks_cluster_name
$VpcId         = terraform "-chdir=.." output -raw vpc_id
$Region        = "us-east-1"
$AlbRoleArn    = terraform "-chdir=.." output -raw alb_controller_role_arn
$ExtDnsRoleArn = terraform "-chdir=.." output -raw external_dns_role_arn
$AutoscalerArn = terraform "-chdir=.." output -raw cluster_autoscaler_role_arn
$Domain        = "anvilops.devopsnexus.io"

## Change "dev" to "staging" or "production" as needed
terraform apply `
  -var="cluster_name=$ClusterName" `
  -var="vpc_id=$VpcId" `
  -var="region=$Region" `
  -var="environment=dev" `
  -var="domain=$Domain" `
  -var="alb_controller_role_arn=$AlbRoleArn" `
  -var="external_dns_role_arn=$ExtDnsRoleArn" `
  -var="cluster_autoscaler_role_arn=$AutoscalerArn" `
  -var="redis_endpoint=placeholder"
```

**Verify all charts are running:**

```bash
kubectl get pods -A | grep -E "external-secrets|external-dns|aws-load-balancer|metrics-server|cluster-autoscaler|keda"
```

```powershell
kubectl get pods -A | Select-String "external-secrets|external-dns|aws-load-balancer|metrics-server|cluster-autoscaler|keda"
```

### Step 7: Build and Push Container Images

**Bash / macOS / Linux:**

```bash
cd ../../../   # back to project root from terraform/platform/helm
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

docker build -t anvilops-api:latest ./backend
docker tag anvilops-api:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:v1.0.0
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:v1.0.0
```

**PowerShell (Windows):**

```powershell
cd ../../../   # back to project root from terraform/platform/helm
$AccountId = aws sts get-caller-identity --query Account --output text
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.us-east-1.amazonaws.com"

docker build -t anvilops-api:latest ./backend
docker tag anvilops-api:latest "$AccountId.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:v1.0.0"
docker push "$AccountId.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:v1.0.0"
```

### Step 8: Deploy to EKS

```bash
cd terraform/platform/k8s

# Wait for External Secrets Operator CRDs to be fully registered before applying.
# The kustomize base includes ExternalSecret and SecretStore resources; if the CRDs
# haven't propagated to the API server yet the apply will fail with "no matches for kind".
kubectl wait --for condition=established --timeout=120s \
  crd/externalsecrets.external-secrets.io \
  crd/secretstores.external-secrets.io

kubectl kustomize overlays/production | kubectl apply -f -
kubectl -n anvilops rollout status deployment/anvilops-api --timeout=300s
```

Or use the deploy script which handles all of this:

```bash
./scripts/deploy-app.sh production
```

```powershell
.\scripts\deploy-app.ps1 production
```

### Step 9: Run Database Migrations

```bash
kubectl -n anvilops exec deploy/anvilops-api -- alembic upgrade head
```

### Step 10: Create Initial Admin User

**Bash / macOS / Linux:**

```bash
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)
aws cognito-idp admin-create-user --user-pool-id $USER_POOL_ID --username admin@example.com --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true --temporary-password "TempPassword123!"
aws cognito-idp admin-add-user-to-group --user-pool-id $USER_POOL_ID --username admin@example.com --group-name admin
```

**PowerShell (Windows):**

```powershell
$UserPoolId = terraform output -raw cognito_user_pool_id
aws cognito-idp admin-create-user --user-pool-id $UserPoolId --username admin@example.com --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true --temporary-password "TempPassword123!"
aws cognito-idp admin-add-user-to-group --user-pool-id $UserPoolId --username admin@example.com --group-name admin
```

### Step 11: Validate

```bash
./scripts/smoke-test.sh
```

```powershell
.\scripts\smoke-test.ps1
```

> **Next:** If smoke tests pass, proceed to [Post-Deployment Configuration](#6-post-deployment-configuration) below.

---

## 6. Post-Deployment Configuration

### Slack Webhook
```bash
aws secretsmanager put-secret-value --secret-id anvilops/slack-webhook --secret-string "https://hooks.slack.com/services/T.../B.../..."
kubectl -n anvilops rollout restart deployment/anvilops-worker
```

### AWX (Ansible)

AWX is now fully automated by Terraform. The Helm chart step (`terraform/platform/helm`) installs the AWX Operator, deploys the AWX instance, creates K8s secrets for the admin password and PostgreSQL connection, stores credentials in AWS Secrets Manager (for the ExternalSecret in the anvilops namespace), and runs a configuration Job that creates the AnvilOps organization, project, inventories, and job templates.

**One manual prerequisite:** Before running the Helm chart step, create the `awx` database in your RDS instance:

```bash
# Connect to RDS via a pod in the cluster
kubectl run psql-client --rm -it --restart=Never --image=postgres:16 -- \
  psql "host=<RDS_ENDPOINT> user=anvilops dbname=anvilops sslmode=require" \
  -c "CREATE DATABASE awx;"
```

See [Section 6a](#6a-awx-configuration-details) for full details on what Terraform creates and how secrets flow.

### Puppet Enterprise

Puppet Enterprise is deployed as an EC2 instance by the platform Terraform module. The `user_data` script automatically:
- Installs PE from the official tarball
- Configures autosigning, Code Manager, and CloudWatch logging
- Generates a 1-year RBAC API token and stores it in Secrets Manager

No manual steps are required for basic operation. See [Section 6b](#6b-puppet-enterprise-details) for verification steps and token details.

### Confirm SNS Subscription
Check inbox for AWS SNS confirmation email and click the link.

---

### 6a. AWX Configuration Details

The Helm chart Terraform module (`terraform/platform/helm/install-charts.tf`) creates these AWX resources:

| Resource | Purpose |
|----------|---------|
| `helm_release.awx_operator` | Installs the AWX Operator (v2.19.1) in the `awx` namespace |
| `kubectl_manifest.awx_admin_password_secret` | K8s Secret with auto-generated admin password |
| `kubectl_manifest.awx_postgres_config_secret` | K8s Secret with RDS connection details for the `awx` database |
| `kubectl_manifest.awx_instance` | AWX custom resource that the operator reconciles into a running AWX deployment |
| `aws_secretsmanager_secret.awx` | Stores AWX URL + credentials in Secrets Manager |
| `kubectl_manifest.awx_config_job` | K8s Job that configures organization, project, inventories, and job templates |

**Secrets flow:**
1. Terraform generates `random_password.awx_admin` and `random_password.awx_db`
2. Passwords are stored in K8s Secrets in the `awx` namespace (used by AWX directly)
3. AWX URL + admin credentials are stored in Secrets Manager (`anvilops/awx-*`)
4. The existing `ExternalSecret` in the `anvilops` namespace syncs from Secrets Manager into the app's K8s Secret

**Variables for the Helm step:**

| Variable | Description | Default |
|----------|-------------|---------|
| `rds_endpoint` | RDS endpoint for AWX PostgreSQL | `""` |
| `awx_git_repo_url` | Git repo URL for AWX project sync | `""` |
| `project_name` | Project name for resource naming | `"anvilops"` |
| `grafana_admin_password` | Grafana admin password | `"admin"` |

**Verify AWX is running:**

```bash
kubectl -n awx get pods
kubectl -n awx get awx
```

---

### 6b. Puppet Enterprise Details

The platform Terraform module (`terraform/platform/modules/puppet/`) provisions:

| Resource | Purpose |
|----------|---------|
| EC2 instance (r5.xlarge) | Runs Puppet Enterprise server |
| EBS volume (gp3) | Persistent `/opt/puppetlabs` storage |
| Secrets Manager secret (console password) | Auto-generated PE console admin password |
| Secrets Manager secret (API token) | RBAC API token (auto-generated by user_data) |
| Route 53 A record | `puppet.<domain>` private DNS |
| CloudWatch log groups | Server, console, PuppetDB, and system logs |
| Security group rules | Ports 443, 4433, 8081, 8140, 8142, 8143 within VPC |

**API token automation:** The `user_data` script waits for PE to be fully running, then:
1. Authenticates to the RBAC API at `https://puppet.<domain>:4433/rbac-api/v1/auth/token`
2. Generates a 1-year token
3. Stores the token in Secrets Manager

**Verify the API token was stored:**

```bash
aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw puppet_api_token_secret_arn) \
  --query SecretString --output text | jq .
```

If the token shows `placeholder-will-be-replaced-by-user-data`, the user_data script has not yet completed. Check the bootstrap log:

```bash
# Connect via SSM Session Manager
aws ssm start-session --target $(terraform output -raw puppet_instance_id)
sudo tail -f /var/log/puppet-bootstrap.log
```

---

### 6c. CI/CD Pipeline Setup

GitHub Actions OIDC integration is available but disabled by default. To enable:

**1. Set Terraform variables:**

```hcl
# In your terraform.tfvars
enable_github_actions_oidc = true
github_actions_repos       = ["your-org/anvilops"]
```

**2. Apply:**

```bash
terraform plan -var-file terraform.dev.tfvars -out tfplan
terraform apply tfplan
```

**3. Configure GitHub repository secrets:**

```bash
ROLE_ARN=$(terraform output -raw github_actions_deploy_role_arn)
echo "Add this as a GitHub Actions secret named AWS_DEPLOY_ROLE_ARN: $ROLE_ARN"
```

In your GitHub repository settings, add these secrets:
- `AWS_DEPLOY_ROLE_ARN` — the role ARN from the output above
- `AWS_REGION` — `us-east-1` (or your primary region)
- `EKS_CLUSTER_NAME` — from `terraform output -raw eks_cluster_name`

**4. EKS auth mapping:**

The GitHub Actions role needs to be mapped in the EKS `aws-auth` ConfigMap or EKS access entries to allow `kubectl` access:

```bash
eksctl create iamidentitymapping \
  --cluster $(terraform output -raw eks_cluster_name) \
  --arn $ROLE_ARN \
  --group system:masters \
  --username github-actions
```

**What Terraform creates:**
- `aws_iam_openid_connect_provider.github_actions` — GitHub OIDC provider (gated by `enable_github_actions_oidc`)
- `aws_iam_role.github_actions_deploy` — Deploy role with trust policy scoped to your repos
- Scoped permissions: ECR push + EKS describe (not the overly broad managed policies)

---

### 6d. Monitoring & Observability

Terraform creates a comprehensive monitoring stack:

**CloudWatch (platform module):**
- SNS topic with email subscription for all alarms
- CloudWatch dashboard with ALB, RDS, Redis, EKS, and ECS panels
- Log groups for API, worker, frontend, and celery-beat services
- Metric filters for error tracking
- Alarms: RDS (CPU, memory, storage, connections, latency), Redis (CPU, memory, connections), ALB (5xx, 4xx, response time, unhealthy hosts), ECS task failures, pod restarts

**kube-prometheus-stack (Helm chart module):**
- Prometheus with 30-day retention and 50Gi persistent storage
- Grafana with persistent storage and configurable admin password
- Alertmanager with 120-hour retention
- ServiceMonitor and PodMonitor selectors enabled for custom metrics

**Verify monitoring is running:**

```bash
# CloudWatch dashboard
aws cloudwatch get-dashboard --dashboard-name anvilops-dev

# Prometheus stack
kubectl -n monitoring get pods

# Access Grafana (port-forward)
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
# Open http://localhost:3000 (admin / <grafana_admin_password>)
```

**Confirm SNS subscription:** Check your email for the AWS SNS confirmation and click the link. Until confirmed, alarm notifications will not be delivered.

---

## 7. Environment Promotion

```bash
# Create dev environment with separate workspace
terraform workspace new dev
terraform plan -var-file terraform.dev.tfvars -out tfplan-dev
terraform apply tfplan-dev
```

Promotion flow: **dev** -> **staging** -> **production**

Tag images with release candidates, deploy to staging, validate, then promote to production.

---

## 8. Updating the Application

### Manual Deployment

**Bash / macOS / Linux:**

```bash
# Run from project root
cd /path/to/anvilops   # adjust to your checkout location
GIT_SHA=$(git rev-parse --short HEAD)
docker build -t anvilops-api:${GIT_SHA} ./backend
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:${GIT_SHA}
kubectl set image deployment/anvilops-api api=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:${GIT_SHA} -n anvilops
```

**PowerShell (Windows):**

```powershell
# Run from project root
Set-Location C:\path\to\anvilops   # adjust to your checkout location
$GitSha = git rev-parse --short HEAD
docker build -t "anvilops-api:$GitSha" ./backend
docker push "$AccountId.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:$GitSha"
kubectl set image deployment/anvilops-api "api=$AccountId.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:$GitSha" -n anvilops
```

### Rollback
```bash
kubectl -n anvilops rollout undo deployment/anvilops-api
```

---

## 9. Scaling Guide

### Horizontal
```bash
kubectl -n anvilops scale deployment/anvilops-api --replicas=5
kubectl -n anvilops scale deployment/anvilops-worker --replicas=4
```

### Vertical
Update `terraform.tfvars` (instance types, classes) and `terraform apply`.

---

## 10. Troubleshooting

| Issue | Command |
|-------|---------|
| State lock stuck | `terraform force-unlock <LOCK_ID>` |
| Pods pending | `kubectl describe pod <name> -n anvilops` |
| ALB 502/503 | Check target group health + security groups |
| DB connection fail | Verify RDS status + SG rules on port 5432 |
| Workers idle | `kubectl logs deploy/anvilops-worker -n anvilops` |
| ExternalSecret CRD missing / v1beta1 error | Install or upgrade External Secrets Operator (>= 0.10 for v1 API): `helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace --set installCRDs=true --wait` |
| General debugging | `kubectl -n anvilops get events --sort-by='.lastTimestamp'` |

### ALB Controller Webhook Race Condition

**Symptom**

```
Error: failed calling webhook 'mservice.elbv2.k8s.aws': no endpoints available for service 'aws-load-balancer-webhook-service'
```

**Cause**

`external_secrets`, `external_dns`, and/or `keda` were installed in parallel with `aws_load_balancer_controller`. The ALB webhook pod was not yet ready when those charts tried to create Services, causing the webhook admission call to fail.

**Fix (already applied)**

`depends_on = [helm_release.aws_load_balancer_controller]` is now set for all dependent charts in `terraform/platform/helm/install-charts.tf`. Re-running `terraform apply` on a fresh cluster will no longer hit this race condition.

**Manual cleanup if you already hit this error**

Remove the orphaned Helm releases and their Terraform state entries, then re-apply:

```bash
# List all helm releases across namespaces
helm list -A

# Remove the failed external-secrets release
helm uninstall external-secrets -n external-secrets

# Remove the failed keda release
helm uninstall keda -n keda

# Remove failed releases from Terraform state so it re-creates them
terraform state rm helm_release.external_secrets
terraform state rm helm_release.keda

# Then re-run
terraform apply
```

---

## 11. Teardown

### Full Teardown

```bash
./scripts/destroy.sh production
```

```powershell
.\scripts\destroy.ps1 production
```

### Manual Steps
1. Delete K8s resources and Helm releases first
2. `terraform destroy` (disable RDS deletion protection first if production)
3. Optionally destroy state backend

---

## 12. Cost Optimization Tips

### Use the Dev/Demo Environment

The fastest way to cut costs is to use the included dev tfvars, which scales every component to its smallest reasonable size:

```bash
terraform plan -var-file terraform.dev.tfvars -out tfplan
terraform apply tfplan
```

| Component | Production | Dev/Demo | Savings |
|-----------|-----------|----------|---------|
| EKS nodes | 3x t3.xlarge | 2x t3.medium | ~$350/mo |
| RDS PostgreSQL | db.r6g.large Multi-AZ | db.t3.small Single-AZ | ~$250/mo |
| ElastiCache Redis | cache.r6g.large x2 | cache.t3.micro x1 | ~$115/mo |
| NAT Gateways | 3 (one per AZ) | 1 (shared) | ~$67/mo |
| Puppet Enterprise | r5.xlarge | t3.large | ~$140/mo |
| WAF | enabled | disabled | ~$25/mo |
| **Monthly total** | **~$1,740** | **~$350** | **~$1,390** |

### Additional Production Optimizations

| Optimization | Savings |
|-------------|---------|
| FARGATE_SPOT for TF runner | 70% on runner tasks |
| Reserved Instances (1-year) | 30-40% on steady-state |
| Savings Plans (compute) | 20-30% across EC2/Fargate |

Monitor costs:

**Bash / macOS / Linux:**

```bash
aws ce get-cost-and-usage --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE
```

**PowerShell (Windows):**

```powershell
$Start = (Get-Date -Day 1).ToString("yyyy-MM-dd")
$End   = (Get-Date).ToString("yyyy-MM-dd")
aws ce get-cost-and-usage --time-period "Start=$Start,End=$End" --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE
```
