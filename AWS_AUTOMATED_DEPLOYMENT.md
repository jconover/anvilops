# AnvilOps -- Automated AWS Deployment Guide

Deploy the entire AnvilOps platform to AWS using Terraform. This guide is the automated counterpart to [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md), which provides the manual step-by-step reference for each component. If you want to understand what each resource does and why, read that document first. If you want to deploy everything with minimal effort, follow this one.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Directory Structure](#3-directory-structure)
4. [Quick Start (TL;DR)](#4-quick-start-tldr)
5. [Step-by-Step Deployment](#5-step-by-step-deployment)
6. [Post-Deployment Configuration](#6-post-deployment-configuration)
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
| Security | IAM roles, IRSA, Secrets Manager, KMS | Least-privilege access, encrypted secrets |
| State Backend | S3 + DynamoDB | Terraform state storage and locking |

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
| kustomize | Latest | Kubernetes manifest overlays |
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
│   └── state-backend/       # S3 + DynamoDB for TF state
├── k8s/
│   ├── base/                # Kustomize base manifests
│   └── overlays/
│       ├── dev/
│       ├── staging/
│       └── production/
├── helm/                    # Helm chart values files
└── scripts/
    ├── bootstrap.sh         # Full deployment
    ├── deploy-app.sh        # App build + deploy
    ├── smoke-test.sh        # Health validation
    └── destroy.sh           # Teardown
```

---

## 4. Quick Start (TL;DR)

```bash
cd terraform/platform

# 1. Configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# 2. Deploy infrastructure (~30 minutes)
./scripts/bootstrap.sh production

# 3. Build and deploy the application (~10 minutes)
./scripts/deploy-app.sh production

# 4. Validate
./scripts/smoke-test.sh

# 5. Open the platform
echo "Visit: https://$(terraform output -raw app_domain)"
```

---

## 5. Step-by-Step Deployment

### Step 1: Configure Variables

```bash
cd terraform/platform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`. Key variables:

| Variable | Dev | Staging | Production |
|----------|-----|---------|------------|
| `single_nat_gateway` | true | true | false |
| `eks_node_desired_size` | 2 | 3 | 4 |
| `rds_instance_class` | db.t3.medium | db.t3.large | db.r6g.large |
| `rds_multi_az` | false | false | true |
| `redis_node_type` | cache.t3.medium | cache.t3.medium | cache.r6g.large |
| `redis_num_cache_clusters` | 1 | 1 | 2 |
| `enable_waf` | false | true | true |

### Step 2: Bootstrap State Backend

One-time operation per AWS account:

```bash
cd terraform/platform/modules/state-backend
terraform init
terraform apply -var="project_name=anvilops" -var="environment=production"
```

Note the output values (`state_bucket_name`, `dynamodb_table_name`).

### Step 3: Initialize Main Platform

```bash
cd terraform/platform
terraform init \
  -backend-config="bucket=<state_bucket_name>" \
  -backend-config="key=platform/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=<dynamodb_table_name>"
```

### Step 4: Plan and Apply

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

~25-30 minutes. Longest resources: EKS (~15min), RDS (~10min), ElastiCache (~8min).

### Step 5: Configure kubectl

```bash
aws eks update-kubeconfig \
  --name $(terraform output -raw eks_cluster_name) \
  --region us-east-1
kubectl get nodes
```

### Step 6: Install Helm Charts

```bash
# ALB Controller, External Secrets, Metrics Server, External DNS, Cluster Autoscaler
# See the helm/ directory for values files
```

### Step 7: Build and Push Container Images

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

docker build -t anvilops-api:latest ./backend
docker tag anvilops-api:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:v1.0.0
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:v1.0.0
```

### Step 8: Deploy to EKS

```bash
cd terraform/platform/k8s
kustomize build overlays/production | kubectl apply -f -
kubectl -n anvilops rollout status deployment/anvilops-api --timeout=300s
```

### Step 9: Run Database Migrations

```bash
kubectl -n anvilops exec deploy/anvilops-api -- alembic upgrade head
```

### Step 10: Create Initial Admin User

```bash
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com \
  --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true \
  --temporary-password "TempPassword123!"
aws cognito-idp admin-add-user-to-group \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com \
  --group-name admin
```

### Step 11: Validate

```bash
./scripts/smoke-test.sh
```

---

## 6. Post-Deployment Configuration

### Slack Webhook
```bash
aws secretsmanager put-secret-value \
  --secret-id anvilops/slack-webhook \
  --secret-string "https://hooks.slack.com/services/T.../B.../..."
kubectl -n anvilops rollout restart deployment/anvilops-worker
```

### AWX (Ansible)
Install AWX operator on EKS. See [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md) for full setup.

### Puppet Enterprise
SSH via SSM, complete PE installation, store API token in Secrets Manager.

### Confirm SNS Subscription
Check inbox for AWS SNS confirmation email and click the link.

---

## 7. Environment Promotion

```bash
# Create dev environment with separate workspace
terraform workspace new dev
terraform plan -var-file=terraform.dev.tfvars -out=tfplan-dev
terraform apply tfplan-dev
```

Promotion flow: **dev** -> **staging** -> **production**

Tag images with release candidates, deploy to staging, validate, then promote to production.

---

## 8. Updating the Application

### Manual Deployment
```bash
GIT_SHA=$(git rev-parse --short HEAD)
docker build -t anvilops-api:${GIT_SHA} ./backend
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:${GIT_SHA}
kubectl set image deployment/anvilops-api api=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:${GIT_SHA} -n anvilops
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
| General debugging | `kubectl -n anvilops get events --sort-by='.lastTimestamp'` |

---

## 11. Teardown

### Full Teardown
```bash
./scripts/destroy.sh production
```

### Manual Steps
1. Delete K8s resources and Helm releases first
2. `terraform destroy` (disable RDS deletion protection first if production)
3. Optionally destroy state backend

---

## 12. Cost Optimization Tips

| Optimization | Savings |
|-------------|---------|
| Single NAT Gateway (dev) | ~$32/mo |
| Smaller EKS nodes (t3.large) | ~$200/mo |
| Smaller RDS (db.t3.medium, no Multi-AZ) | ~$300/mo |
| Smaller Redis (cache.t3.medium, 1 node) | ~$300/mo |
| FARGATE_SPOT for TF runner | 70% on runner tasks |
| Reserved Instances (1-year) | 30-40% on steady-state |
| **Dev total** | **~$450/mo** vs $1,740 production |

Monitor costs:
```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE
```
