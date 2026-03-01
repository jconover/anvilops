# AnvilOps — AWS Production Deployment Guide

Complete guide for deploying the AnvilOps server provisioning platform to AWS. This document covers every component from networking to observability, written for a production-grade deployment across two regions.

> **Shell compatibility note:** Command examples use `\` for line continuation (Linux/macOS). On **PowerShell**, replace `\` with a backtick (`` ` ``) or join the command onto a single line. For a cross-platform quickstart, see [AWS_AUTOMATED_DEPLOYMENT.md](./AWS_AUTOMATED_DEPLOYMENT.md).

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [AWS Account & Networking](#3-aws-account--networking)
4. [EKS Cluster](#4-eks-cluster)
5. [RDS PostgreSQL](#5-rds-postgresql)
6. [ElastiCache Redis & Celery Workers](#6-elasticache-redis--celery-workers)
7. [Terraform State & ECS Fargate Runner](#7-terraform-state--ecs-fargate-runner)
8. [Security, IAM & Cognito](#8-security-iam--cognito)
9. [Container Images & ECR](#9-container-images--ecr)
10. [Kubernetes Deployments](#10-kubernetes-deployments)
11. [AWX Deployment](#11-awx-deployment)
12. [Puppet Enterprise](#12-puppet-enterprise)
13. [DNS & Load Balancing](#13-dns--load-balancing)
14. [CI/CD Pipeline](#14-cicd-pipeline)
15. [Observability & Monitoring](#15-observability--monitoring)
16. [Testing & Validation](#16-testing--validation)
17. [Operational Runbook](#17-operational-runbook)
18. [Cost Estimate](#18-cost-estimate)

---

## 1. Architecture Overview

```
                          ┌─────────────────────────────────────────┐
                          │           Route 53 (DNS)                │
                          │   anvilops.example.com                  │
                          └────────────┬────────────────────────────┘
                                       │
                          ┌────────────▼────────────────────────────┐
                          │   Application Load Balancer (ALB)       │
                          │   HTTPS :443 (ACM certificate)          │
                          │   WAF v2 attached                       │
                          └────────────┬────────────────────────────┘
                                       │
                ┌──────────────────────▼──────────────────────────┐
                │              EKS Cluster (us-east-1)            │
                │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
                │  │ Next.js  │  │ FastAPI  │  │ Celery       │  │
                │  │ Frontend │  │ Backend  │  │ Workers (3)  │  │
                │  │ (3 pods) │  │ (3 pods) │  │              │  │
                │  └──────────┘  └──────────┘  └──────┬───────┘  │
                │                                      │          │
                │  ┌──────────┐  ┌──────────────────┐  │          │
                │  │ AWX      │  │ Puppet           │  │          │
                │  │ Operator │  │ Enterprise (EC2) │◄─┘          │
                │  └──────────┘  └──────────────────┘             │
                └──────────────────────┬──────────────────────────┘
                                       │
          ┌───────────────┬────────────┼────────────┐
          │               │            │            │
   ┌──────▼──────┐ ┌──────▼──────┐ ┌──▼─────┐ ┌───▼───────────┐
   │ RDS Postgres│ │ ElastiCache │ │  S3    │ │ ECS Fargate   │
   │ Multi-AZ    │ │ Redis       │ │ TF     │ │ (Terraform    │
   │ (db.r6g.lg) │ │ (2 nodes)  │ │ State  │ │  Runner)      │
   └─────────────┘ └─────────────┘ └────────┘ └───────────────┘
```

### Component Summary

| Component | Service | Purpose |
|-----------|---------|---------|
| Frontend | EKS (Next.js pods) | Server builder wizard, dashboards |
| Backend API | EKS (FastAPI pods) | REST API, auth, business logic |
| Task Workers | EKS (Celery pods) | Async orchestration pipeline |
| Database | RDS PostgreSQL 16 | Persistent state, server requests |
| Cache/Broker | ElastiCache Redis 7 | Celery broker + result backend |
| Terraform Runner | ECS Fargate | Ephemeral terraform plan/apply tasks |
| TF State | S3 (native locking) | Terraform state storage and locking per server |
| Configuration | AWX on EKS | Day-1 Ansible playbook execution |
| Compliance | Puppet Enterprise (EC2) | Day-2+ drift detection, enforcement |
| Auth | AWS Cognito | User authentication (OIDC) |
| DNS | Route 53 | Public + internal DNS records |
| CDN/WAF | CloudFront + WAF v2 | Edge caching, security rules |
| Secrets | Secrets Manager | Database passwords, API tokens |
| Monitoring | CloudWatch + Prometheus | Metrics, logs, alerting |

### Regions

| Region | Purpose |
|--------|---------|
| `us-east-1` | Primary — all platform services |
| `us-west-2` | Secondary — target for provisioned servers |

---

## 2. Prerequisites

### Required Tools

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | v2 | `curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip && unzip awscliv2.zip && sudo ./aws/install` |
| kubectl | 1.29+ | `curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"` |
| eksctl | Latest | `curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz"` |
| Terraform | >= 1.5.0 | `tfenv install 1.9.8 && tfenv use 1.9.8` |
| Helm | v3 | `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` |
| Docker | Latest | For building container images |
| jq | Latest | JSON parsing in scripts |

### AWS Account Setup

```bash
# Configure AWS CLI with your credentials
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region name: us-east-1
# Default output format: json

# Verify access
aws sts get-caller-identity
```

### Required AWS Permissions

The deploying IAM user/role needs these managed policies (or equivalent custom policies):

- `AmazonEKSClusterPolicy`
- `AmazonEKSWorkerNodePolicy`
- `AmazonVPCFullAccess`
- `AmazonRDSFullAccess`
- `AmazonElastiCacheFullAccess`
- `AmazonS3FullAccess`
- `AmazonDynamoDBFullAccess`
- `AmazonECS_FullAccess`
- `AmazonEC2FullAccess`
- `AmazonRoute53FullAccess`
- `AmazonCognitoPowerUser`
- `SecretsManagerReadWrite`
- `IAMFullAccess`
- `AWSCertificateManagerFullAccess`
- `ElasticLoadBalancingFullAccess`
- `CloudWatchFullAccess`

> **Production note**: Create a dedicated deployment IAM role with least-privilege custom policies rather than using these broad managed policies.

---

## 3. AWS Account & Networking

### 3.1 VPC Architecture

AnvilOps uses a multi-tier VPC design with public, private, and isolated subnets across three Availability Zones.

```
┌──────────────────────────────────────────────────────────────┐
│  VPC: 10.0.0.0/16 (anvilops-platform)                       │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  Public Subnets  │  │ Private Subnets  │  │  Isolated    │ │
│  │  10.0.1.0/24     │  │ 10.0.10.0/24    │  │  10.0.20.0/24│ │
│  │  10.0.2.0/24     │  │ 10.0.11.0/24    │  │  10.0.21.0/24│ │
│  │  10.0.3.0/24     │  │ 10.0.12.0/24    │  │  10.0.22.0/24│ │
│  │                  │  │                  │  │              │ │
│  │  ALB, NAT GW     │  │  EKS, ECS, EC2  │  │  RDS, Redis  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│                                                              │
│  Internet Gateway ─── NAT Gateways (one per AZ)             │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Create the VPC

```bash
# Create VPC
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=anvilops-platform},{Key=Environment,Value=production}]' \
  --query 'Vpc.VpcId' --output text)

# Enable DNS support
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames
```

### 3.3 Create Subnets

```bash
# Public subnets (ALB, NAT Gateway)
for i in 1 2 3; do
  AZ=$(aws ec2 describe-availability-zones --query "AvailabilityZones[$((i-1))].ZoneName" --output text)
  aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.${i}.0/24" \
    --availability-zone $AZ \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=anvilops-public-${i}},{Key=kubernetes.io/role/elb,Value=1},{Key=Tier,Value=public}]"
done

# Private subnets (EKS, ECS, application workloads)
for i in 10 11 12; do
  AZ=$(aws ec2 describe-availability-zones --query "AvailabilityZones[$((i-10))].ZoneName" --output text)
  aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.${i}.0/24" \
    --availability-zone $AZ \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=anvilops-private-${i}},{Key=kubernetes.io/role/internal-elb,Value=1},{Key=Tier,Value=private}]"
done

# Isolated subnets (RDS, ElastiCache — no internet access)
for i in 20 21 22; do
  AZ=$(aws ec2 describe-availability-zones --query "AvailabilityZones[$((i-20))].ZoneName" --output text)
  aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.${i}.0/24" \
    --availability-zone $AZ \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=anvilops-isolated-${i}},{Key=Tier,Value=isolated}]"
done
```

### 3.4 Internet Gateway & NAT Gateways

```bash
# Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=anvilops-igw}]' \
  --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# Elastic IPs for NAT Gateways
EIP_1=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)
EIP_2=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)

# NAT Gateways (one per AZ for HA — use 2 minimum)
PUBLIC_SUBNET_1=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=anvilops-public-1" \
  --query 'Subnets[0].SubnetId' --output text)
PUBLIC_SUBNET_2=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=anvilops-public-2" \
  --query 'Subnets[0].SubnetId' --output text)

NAT_1=$(aws ec2 create-nat-gateway \
  --subnet-id $PUBLIC_SUBNET_1 --allocation-id $EIP_1 \
  --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=anvilops-nat-1}]' \
  --query 'NatGateway.NatGatewayId' --output text)

NAT_2=$(aws ec2 create-nat-gateway \
  --subnet-id $PUBLIC_SUBNET_2 --allocation-id $EIP_2 \
  --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=anvilops-nat-2}]' \
  --query 'NatGateway.NatGatewayId' --output text)

echo "Wait for NAT gateways to become available..."
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_1 $NAT_2
```

### 3.5 Route Tables

```bash
# Public route table (internet via IGW)
PUBLIC_RT=$(aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=anvilops-public-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PUBLIC_RT --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID

# Associate public subnets
for SUBNET_NAME in anvilops-public-1 anvilops-public-2 anvilops-public-3; do
  SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=$SUBNET_NAME" --query 'Subnets[0].SubnetId' --output text)
  aws ec2 associate-route-table --route-table-id $PUBLIC_RT --subnet-id $SUBNET_ID
  aws ec2 modify-subnet-attribute --subnet-id $SUBNET_ID --map-public-ip-on-launch
done

# Private route tables (internet via NAT)
PRIVATE_RT_1=$(aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=anvilops-private-rt-1}]' \
  --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PRIVATE_RT_1 --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_1

PRIVATE_RT_2=$(aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=anvilops-private-rt-2}]' \
  --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PRIVATE_RT_2 --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_2

# Associate private subnets (split across NATs)
PRIV_SUB_10=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=anvilops-private-10" --query 'Subnets[0].SubnetId' --output text)
PRIV_SUB_11=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=anvilops-private-11" --query 'Subnets[0].SubnetId' --output text)
PRIV_SUB_12=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=anvilops-private-12" --query 'Subnets[0].SubnetId' --output text)

aws ec2 associate-route-table --route-table-id $PRIVATE_RT_1 --subnet-id $PRIV_SUB_10
aws ec2 associate-route-table --route-table-id $PRIVATE_RT_1 --subnet-id $PRIV_SUB_12
aws ec2 associate-route-table --route-table-id $PRIVATE_RT_2 --subnet-id $PRIV_SUB_11

# Isolated subnets — no route table changes (no internet access)
```

### 3.6 Security Groups

```bash
# ALB Security Group
ALB_SG=$(aws ec2 create-security-group \
  --group-name anvilops-alb-sg \
  --description "AnvilOps ALB - public HTTPS" \
  --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $ALB_SG --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $ALB_SG --protocol tcp --port 80 --cidr 0.0.0.0/0

# EKS Node Security Group
EKS_SG=$(aws ec2 create-security-group \
  --group-name anvilops-eks-nodes-sg \
  --description "AnvilOps EKS worker nodes" \
  --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $EKS_SG --protocol tcp --port 8000 --source-group $ALB_SG
aws ec2 authorize-security-group-ingress --group-id $EKS_SG --protocol tcp --port 3000 --source-group $ALB_SG
aws ec2 authorize-security-group-ingress --group-id $EKS_SG --protocol -1 --source-group $EKS_SG

# RDS Security Group
RDS_SG=$(aws ec2 create-security-group \
  --group-name anvilops-rds-sg \
  --description "AnvilOps RDS PostgreSQL" \
  --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $RDS_SG --protocol tcp --port 5432 --source-group $EKS_SG

# Redis Security Group
REDIS_SG=$(aws ec2 create-security-group \
  --group-name anvilops-redis-sg \
  --description "AnvilOps ElastiCache Redis" \
  --vpc-id $VPC_ID --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $REDIS_SG --protocol tcp --port 6379 --source-group $EKS_SG
```

### 3.7 Workload VPCs (Server Provisioning Targets)

Create separate VPCs for servers provisioned by AnvilOps. These are the VPCs users select in the server builder wizard.

```bash
# Dev workload VPC (us-east-1)
aws ec2 create-vpc --cidr-block 10.10.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=anvilops-workload-dev},{Key=Environment,Value=dev},{Key=ManagedBy,Value=AnvilOps}]'

# Staging workload VPC (us-east-1)
aws ec2 create-vpc --cidr-block 10.20.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=anvilops-workload-staging},{Key=Environment,Value=staging},{Key=ManagedBy,Value=AnvilOps}]'

# Production workload VPC (us-east-1)
aws ec2 create-vpc --cidr-block 10.30.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=anvilops-workload-prod},{Key=Environment,Value=production},{Key=ManagedBy,Value=AnvilOps}]'

# us-west-2 workload VPCs (repeat for second region)
# Use CIDR ranges 10.110.0.0/16, 10.120.0.0/16, 10.130.0.0/16
```

> **Note:** Each workload VPC needs public, private, and isolated subnets + NAT gateways following the same pattern as the platform VPC. The backend's `/api/v1/regions/{region}/vpcs` endpoint discovers these VPCs dynamically.

---

## 4. EKS Cluster

### 4.1 Create Cluster

```bash
eksctl create cluster \
  --name anvilops \
  --region us-east-1 \
  --version 1.29 \
  --vpc-private-subnets "$PRIV_SUB_10,$PRIV_SUB_11,$PRIV_SUB_12" \
  --vpc-public-subnets "$PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2" \
  --without-nodegroup \
  --tags "Environment=production,ManagedBy=AnvilOps"
```

### 4.2 Create Managed Node Groups

```bash
# Application node group (API, Frontend, Celery)
eksctl create nodegroup \
  --cluster anvilops \
  --name app-nodes \
  --region us-east-1 \
  --node-type t3.xlarge \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 6 \
  --node-private-networking \
  --managed \
  --asg-access \
  --labels "workload=application" \
  --tags "Environment=production"

# AWX node group (AWX requires more resources)
eksctl create nodegroup \
  --cluster anvilops \
  --name awx-nodes \
  --region us-east-1 \
  --node-type m5.xlarge \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3 \
  --node-private-networking \
  --managed \
  --labels "workload=awx" \
  --tags "Environment=production"
```

### 4.3 Install Core Add-ons

```bash
# Update kubeconfig
aws eks update-kubeconfig --name anvilops --region us-east-1

# AWS Load Balancer Controller (for ALB Ingress)
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName=anvilops \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller

# Cluster Autoscaler
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm install cluster-autoscaler autoscaler/cluster-autoscaler \
  --namespace kube-system \
  --set autoDiscovery.clusterName=anvilops \
  --set awsRegion=us-east-1

# Metrics Server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# ExternalDNS (auto-create Route 53 records)
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns
helm install external-dns external-dns/external-dns \
  --namespace kube-system \
  --set provider=aws \
  --set domainFilters[0]=anvilops.example.com \
  --set policy=sync \
  --set aws.zoneType=public
```

### 4.4 Create Namespaces

```bash
kubectl create namespace anvilops
kubectl create namespace awx
kubectl create namespace monitoring
kubectl create namespace cert-manager

# Label for network policies
kubectl label namespace anvilops app=anvilops
kubectl label namespace awx app=awx
```

### 4.5 Install cert-manager (for TLS)

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --set installCRDs=true
```

---

## 5. RDS PostgreSQL

### 5.1 Create Subnet Group

```bash
# Collect isolated subnet IDs
ISO_SUB_20=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=anvilops-isolated-20" --query 'Subnets[0].SubnetId' --output text)
ISO_SUB_21=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=anvilops-isolated-21" --query 'Subnets[0].SubnetId' --output text)
ISO_SUB_22=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=anvilops-isolated-22" --query 'Subnets[0].SubnetId' --output text)

aws rds create-db-subnet-group \
  --db-subnet-group-name anvilops-db-subnets \
  --db-subnet-group-description "AnvilOps RDS isolated subnets" \
  --subnet-ids "$ISO_SUB_20" "$ISO_SUB_21" "$ISO_SUB_22"
```

### 5.2 Store Database Password

```bash
# Generate a strong password and store in Secrets Manager
DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)

aws secretsmanager create-secret \
  --name anvilops/rds/master-password \
  --description "AnvilOps RDS master password" \
  --secret-string "$DB_PASSWORD"

echo "Save this password reference — it will be used for DATABASE_URL"
```

### 5.3 Create RDS Instance

```bash
aws rds create-db-instance \
  --db-instance-identifier anvilops-db \
  --db-instance-class db.r6g.large \
  --engine postgres \
  --engine-version "16.4" \
  --master-username anvilops \
  --master-user-password "$DB_PASSWORD" \
  --allocated-storage 100 \
  --max-allocated-storage 500 \
  --storage-type gp3 \
  --storage-encrypted \
  --kms-key-id alias/aws/rds \
  --db-name anvilops \
  --db-subnet-group-name anvilops-db-subnets \
  --vpc-security-group-ids "$RDS_SG" \
  --multi-az \
  --backup-retention-period 14 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:05:00-sun:06:00" \
  --deletion-protection \
  --copy-tags-to-snapshot \
  --monitoring-interval 60 \
  --monitoring-role-arn "arn:aws:iam::role/rds-monitoring-role" \
  --enable-performance-insights \
  --performance-insights-retention-period 7 \
  --tags Key=Environment,Value=production Key=ManagedBy,Value=AnvilOps \
  --no-publicly-accessible

echo "Waiting for RDS instance to become available (10-15 minutes)..."
aws rds wait db-instance-available --db-instance-identifier anvilops-db
```

### 5.4 Get Connection Endpoint

```bash
RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier anvilops-db \
  --query 'DBInstances[0].Endpoint.Address' --output text)

echo "RDS Endpoint: $RDS_ENDPOINT"
echo "Connection URL: postgresql+asyncpg://anvilops:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/anvilops"
```

### 5.5 Configure Parameter Group

```bash
aws rds create-db-parameter-group \
  --db-parameter-group-name anvilops-pg16 \
  --db-parameter-group-family postgres16 \
  --description "AnvilOps PostgreSQL 16 tuning"

aws rds modify-db-parameter-group \
  --db-parameter-group-name anvilops-pg16 \
  --parameters \
    "ParameterName=shared_buffers,ParameterValue={DBInstanceClassMemory/4},ApplyMethod=pending-reboot" \
    "ParameterName=effective_cache_size,ParameterValue={DBInstanceClassMemory*3/4},ApplyMethod=pending-reboot" \
    "ParameterName=work_mem,ParameterValue=65536,ApplyMethod=immediate" \
    "ParameterName=maintenance_work_mem,ParameterValue=524288,ApplyMethod=immediate" \
    "ParameterName=max_connections,ParameterValue=200,ApplyMethod=pending-reboot" \
    "ParameterName=log_min_duration_statement,ParameterValue=1000,ApplyMethod=immediate" \
    "ParameterName=idle_in_transaction_session_timeout,ParameterValue=300000,ApplyMethod=immediate"

# Apply parameter group to instance
aws rds modify-db-instance \
  --db-instance-identifier anvilops-db \
  --db-parameter-group-name anvilops-pg16 \
  --apply-immediately
```

### 5.6 Run Migrations

```bash
# From a bastion host or EKS pod with database access:
# Option A: Run via kubectl exec into API pod (after deployment)
kubectl exec -n anvilops deploy/anvilops-api -- alembic upgrade head

# Option B: Run from a temporary pod
kubectl run alembic-migrate --rm -it \
  --namespace anvilops \
  --image <YOUR_ECR_REPO>/anvilops-api:latest \
  --env="DATABASE_URL=postgresql+asyncpg://anvilops:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/anvilops" \
  -- alembic upgrade head
```

---

## 6. ElastiCache Redis & Celery Workers

### 6.1 Create ElastiCache Subnet Group

```bash
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name anvilops-redis-subnets \
  --cache-subnet-group-description "AnvilOps Redis isolated subnets" \
  --subnet-ids "$ISO_SUB_20" "$ISO_SUB_21" "$ISO_SUB_22"
```

### 6.2 Create Redis Replication Group

```bash
aws elasticache create-replication-group \
  --replication-group-id anvilops-redis \
  --replication-group-description "AnvilOps Celery broker and result backend" \
  --engine redis \
  --engine-version "7.1" \
  --cache-node-type cache.r6g.large \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --cache-subnet-group-name anvilops-redis-subnets \
  --security-group-ids "$REDIS_SG" \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --snapshot-retention-limit 7 \
  --snapshot-window "04:00-05:00" \
  --preferred-maintenance-window "sun:06:00-sun:07:00" \
  --cache-parameter-group-name default.redis7 \
  --tags Key=Environment,Value=production Key=ManagedBy,Value=AnvilOps

echo "Waiting for Redis cluster to become available (5-10 minutes)..."
aws elasticache wait replication-group-available --replication-group-id anvilops-redis
```

### 6.3 Get Redis Endpoint

```bash
REDIS_ENDPOINT=$(aws elasticache describe-replication-groups \
  --replication-group-id anvilops-redis \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address' --output text)

REDIS_PORT=$(aws elasticache describe-replication-groups \
  --replication-group-id anvilops-redis \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Port' --output text)

echo "Redis Endpoint: $REDIS_ENDPOINT:$REDIS_PORT"
echo "Redis URL: rediss://${REDIS_ENDPOINT}:${REDIS_PORT}/0"
```

> **Note:** Use `rediss://` (double s) for TLS-encrypted connections to ElastiCache.

### 6.4 Celery Worker Configuration

AnvilOps uses three Celery task queues with dedicated worker pools:

| Queue | Workers | Concurrency | Tasks |
|-------|---------|-------------|-------|
| `default` | 2 pods | 4 each | Orchestrator, validation, CMDB sync |
| `terraform` | 2 pods | 2 each | Terraform plan/apply/destroy |
| `notifications` | 1 pod | 4 | Slack, email, in-app notifications |

The Kubernetes deployment for workers is in [Section 10](#10-kubernetes-deployments).

---

## 7. Terraform State & ECS Fargate Runner

### 7.1 Terraform State Backend (S3 with Native Locking)

State locking uses S3 conditional writes (`use_lockfile = true`) instead of DynamoDB (deprecated in Terraform 1.10+).

```bash
# S3 bucket for state files (one per workspace = one per server)
aws s3api create-bucket \
  --bucket anvilops-terraform-state \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket anvilops-terraform-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket anvilops-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
  }'

aws s3api put-public-access-block \
  --bucket anvilops-terraform-state \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### 7.2 ECS Fargate Setup for Terraform Runner

AnvilOps runs Terraform as ephemeral ECS Fargate tasks triggered by Celery. Each `terraform plan` or `terraform apply` spins up a short-lived container, runs the command, and exits.

```bash
# Create ECS cluster
aws ecs create-cluster \
  --cluster-name anvilops-terraform \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy \
    capacityProvider=FARGATE,weight=1,base=0 \
    capacityProvider=FARGATE_SPOT,weight=3,base=0 \
  --tags key=Environment,value=production

# Create CloudWatch log group for Terraform tasks
aws logs create-log-group --log-group-name /ecs/anvilops-terraform
aws logs put-retention-policy --log-group-name /ecs/anvilops-terraform --retention-in-days 30
```

### 7.3 Terraform Runner Task Definition

```bash
# Create ECS Task Execution Role
aws iam create-role \
  --role-name anvilops-terraform-execution \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
aws iam attach-role-policy \
  --role-name anvilops-terraform-execution \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create ECS Task Role (what Terraform itself uses)
aws iam create-role \
  --role-name anvilops-terraform-task \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Terraform needs EC2, VPC, IAM, EBS, Route53 permissions to provision servers
aws iam put-role-policy \
  --role-name anvilops-terraform-task \
  --policy-name terraform-provisioning \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "ec2:*",
          "iam:PassRole",
          "iam:CreateRole",
          "iam:AttachRolePolicy",
          "iam:CreateInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:GetRole",
          "iam:GetInstanceProfile",
          "iam:DeleteRole",
          "iam:DetachRolePolicy",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:DeleteInstanceProfile",
          "route53:ChangeResourceRecordSets",
          "route53:GetHostedZone",
          "route53:ListResourceRecordSets",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ],
        "Resource": "*"
      }
    ]
  }'
```

### 7.4 Register Task Definition

```json
// Save as terraform-task-definition.json
{
  "family": "anvilops-terraform",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/anvilops-terraform-execution",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/anvilops-terraform-task",
  "containerDefinitions": [
    {
      "name": "terraform",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-terraform:latest",
      "essential": true,
      "environment": [
        {"name": "TF_IN_AUTOMATION", "value": "1"},
        {"name": "TF_INPUT", "value": "0"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/anvilops-terraform",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "terraform"
        }
      }
    }
  ]
}
```

```bash
aws ecs register-task-definition --cli-input-json file://terraform-task-definition.json
```

### 7.5 Terraform Backend Configuration

Each Terraform environment (`terraform/environments/dev|staging|production`) should be configured to use S3 state:

```hcl
# terraform/environments/dev/backend.tf
terraform {
  backend "s3" {
    bucket       = "anvilops-terraform-state"
    key          = "servers/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
```

Each server build creates a unique workspace: `server-{request_id}`. This gives complete isolation — one server's state can never affect another.

---

## 8. Security, IAM & Cognito

### 8.1 IRSA (IAM Roles for Service Accounts)

EKS pods use IRSA to access AWS services without static credentials.

```bash
# Enable OIDC provider for the cluster
eksctl utils associate-iam-oidc-provider --cluster anvilops --region us-east-1 --approve

OIDC_PROVIDER=$(aws eks describe-cluster --name anvilops --region us-east-1 \
  --query 'cluster.identity.oidc.issuer' --output text | sed 's|https://||')
```

#### API Pod Service Account

```bash
# Create IAM role for the API pods
eksctl create iamserviceaccount \
  --cluster anvilops \
  --namespace anvilops \
  --name anvilops-api-sa \
  --role-name anvilops-api-role \
  --attach-policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite \
  --attach-policy-arn arn:aws:iam::aws:policy/AmazonCognitoPowerUser \
  --approve
```

#### Celery Worker Service Account

```bash
eksctl create iamserviceaccount \
  --cluster anvilops \
  --namespace anvilops \
  --name anvilops-worker-sa \
  --role-name anvilops-worker-role \
  --attach-policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite \
  --attach-policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess \
  --approve

# Add custom policy for Terraform state access
aws iam put-role-policy \
  --role-name anvilops-worker-role \
  --policy-name terraform-state-access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket"],
        "Resource": ["arn:aws:s3:::anvilops-terraform-state","arn:aws:s3:::anvilops-terraform-state/*"]
      },
      {
        "Effect": "Allow",
        "Action": ["dynamodb:GetItem","dynamodb:PutItem","dynamodb:DeleteItem"],
        "Resource": "arn:aws:dynamodb:us-east-1:*:table/anvilops-terraform-locks"
      },
      {
        "Effect": "Allow",
        "Action": ["ecs:RunTask","ecs:DescribeTasks","ecs:StopTask","iam:PassRole"],
        "Resource": "*"
      }
    ]
  }'
```

### 8.2 AWS Cognito User Pool

```bash
# Create User Pool
POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name AnvilOps \
  --auto-verified-attributes email \
  --username-attributes email \
  --mfa-configuration OFF \
  --password-policy \
    MinimumLength=12,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=true \
  --schema \
    Name=email,Required=true,Mutable=true \
    Name=name,Required=true,Mutable=true \
    Name=custom:role,Required=false,Mutable=true,AttributeDataType=String \
  --admin-create-user-config AllowAdminCreateUserOnly=true \
  --tags Environment=production,ManagedBy=AnvilOps \
  --query 'UserPool.Id' --output text)

echo "User Pool ID: $POOL_ID"

# Create App Client
CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name anvilops-web \
  --generate-secret \
  --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --supported-identity-providers COGNITO \
  --callback-urls "https://anvilops.example.com/auth/callback" \
  --logout-urls "https://anvilops.example.com/auth/login" \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client \
  --access-token-validity 1 \
  --id-token-validity 1 \
  --refresh-token-validity 30 \
  --token-validity-units AccessToken=hours,IdToken=hours,RefreshToken=days \
  --query 'UserPoolClient.ClientId' --output text)

echo "App Client ID: $CLIENT_ID"

# Store client secret
CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-id $CLIENT_ID \
  --query 'UserPoolClient.ClientSecret' --output text)

aws secretsmanager create-secret \
  --name anvilops/cognito/client-secret \
  --secret-string "$CLIENT_SECRET"
```

### 8.3 Create RBAC Groups in Cognito

```bash
# Create groups matching AnvilOps RBAC model
for ROLE in viewer builder builder-prod approver admin; do
  aws cognito-idp create-group \
    --user-pool-id $POOL_ID \
    --group-name $ROLE \
    --description "AnvilOps $ROLE role"
done

# Create initial admin user
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username admin@example.com \
  --user-attributes Name=email,Value=admin@example.com Name=name,Value="Admin User" \
  --temporary-password "TempPass123!"

aws cognito-idp admin-add-user-to-group \
  --user-pool-id $POOL_ID \
  --username admin@example.com \
  --group-name admin
```

### 8.4 Store All Secrets

```bash
# Store all connection strings and tokens in Secrets Manager
aws secretsmanager create-secret \
  --name anvilops/database-url \
  --secret-string "postgresql+asyncpg://anvilops:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/anvilops"

aws secretsmanager create-secret \
  --name anvilops/redis-url \
  --secret-string "rediss://${REDIS_ENDPOINT}:${REDIS_PORT}/0"

aws secretsmanager create-secret \
  --name anvilops/cognito-config \
  --secret-string "{
    \"pool_id\": \"$POOL_ID\",
    \"client_id\": \"$CLIENT_ID\",
    \"client_secret\": \"$CLIENT_SECRET\",
    \"region\": \"us-east-1\"
  }"
```

---

## 9. Container Images & ECR

### 9.1 Create ECR Repositories

```bash
for REPO in anvilops-api anvilops-frontend anvilops-terraform; do
  aws ecr create-repository \
    --repository-name $REPO \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 \
    --tags Key=Environment,Value=production
done
```

### 9.2 Build and Push Backend Image

```bash
# Login to ECR
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build API image (also used for Celery workers)
docker build -t anvilops-api:latest ./backend
docker tag anvilops-api:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
```

### 9.3 Create Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
# ---- Dependencies ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- Builder ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- Runtime ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
```

> **Note:** For standalone output mode, add `output: 'standalone'` to `next.config.mjs`.

```bash
# Build and push frontend
docker build -t anvilops-frontend:latest ./frontend
docker tag anvilops-frontend:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-frontend:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-frontend:latest
```

### 9.4 Build Terraform Runner Image

```bash
# The backend Dockerfile already includes Terraform — reuse it
docker tag anvilops-api:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-terraform:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/anvilops-terraform:latest
```

---

## 10. Kubernetes Deployments

### 10.1 Create Kubernetes Secret

```bash
kubectl create secret generic anvilops-secrets \
  --namespace anvilops \
  --from-literal=DATABASE_URL="postgresql+asyncpg://anvilops:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/anvilops" \
  --from-literal=REDIS_URL="rediss://${REDIS_ENDPOINT}:${REDIS_PORT}/0" \
  --from-literal=SLACK_WEBHOOK_URL="" \
  --from-literal=SLACK_SIGNING_SECRET="" \
  --from-literal=PUPPET_API_TOKEN="" \
  --from-literal=AWX_PASSWORD="" \
  --from-literal=SERVICENOW_PASSWORD=""
```

### 10.2 FastAPI Backend Deployment

Save as `k8s/api-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvilops-api
  namespace: anvilops
  labels:
    app: anvilops-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: anvilops-api
  template:
    metadata:
      labels:
        app: anvilops-api
    spec:
      serviceAccountName: anvilops-api-sa
      nodeSelector:
        workload: application
      containers:
        - name: api
          image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: anvilops-secrets
          env:
            - name: PROJECT_NAME
              value: "AnvilOps"
            - name: DEBUG
              value: "false"
            - name: AWX_BASE_URL
              value: "http://awx-service.awx.svc.cluster.local:80"
            - name: PUPPET_BASE_URL
              value: "https://puppet.anvilops.internal"
            - name: SLACK_ENABLED
              value: "true"
            - name: SLACK_CHANNEL
              value: "#anvilops-builds"
            - name: SLACK_APP_URL
              value: "https://anvilops.example.com"
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: anvilops-api
  namespace: anvilops
spec:
  selector:
    app: anvilops-api
  ports:
    - port: 8000
      targetPort: 8000
  type: ClusterIP
```

### 10.3 Next.js Frontend Deployment

Save as `k8s/frontend-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvilops-frontend
  namespace: anvilops
  labels:
    app: anvilops-frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: anvilops-frontend
  template:
    metadata:
      labels:
        app: anvilops-frontend
    spec:
      nodeSelector:
        workload: application
      containers:
        - name: frontend
          image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-frontend:latest
          ports:
            - containerPort: 3000
          env:
            - name: NEXT_PUBLIC_API_URL
              value: "http://anvilops-api.anvilops.svc.cluster.local:8000"
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: anvilops-frontend
  namespace: anvilops
spec:
  selector:
    app: anvilops-frontend
  ports:
    - port: 3000
      targetPort: 3000
  type: ClusterIP
```

### 10.4 Celery Worker Deployments

Save as `k8s/worker-deployment.yaml`:

```yaml
# Default queue workers (orchestrator, validation, CMDB)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvilops-worker-default
  namespace: anvilops
  labels:
    app: anvilops-worker
    queue: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: anvilops-worker
      queue: default
  template:
    metadata:
      labels:
        app: anvilops-worker
        queue: default
    spec:
      serviceAccountName: anvilops-worker-sa
      nodeSelector:
        workload: application
      containers:
        - name: worker
          image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
          command:
            - celery
            - -A
            - app.worker.celery_app
            - worker
            - --loglevel=info
            - --concurrency=4
            - -Q
            - default
          envFrom:
            - secretRef:
                name: anvilops-secrets
          env:
            - name: AWX_BASE_URL
              value: "http://awx-service.awx.svc.cluster.local:80"
            - name: PUPPET_BASE_URL
              value: "https://puppet.anvilops.internal"
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 2Gi
---
# Terraform queue workers
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvilops-worker-terraform
  namespace: anvilops
  labels:
    app: anvilops-worker
    queue: terraform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: anvilops-worker
      queue: terraform
  template:
    metadata:
      labels:
        app: anvilops-worker
        queue: terraform
    spec:
      serviceAccountName: anvilops-worker-sa
      nodeSelector:
        workload: application
      containers:
        - name: worker
          image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
          command:
            - celery
            - -A
            - app.worker.celery_app
            - worker
            - --loglevel=info
            - --concurrency=2
            - -Q
            - terraform
          envFrom:
            - secretRef:
                name: anvilops-secrets
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 2Gi
---
# Notification queue workers
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvilops-worker-notifications
  namespace: anvilops
  labels:
    app: anvilops-worker
    queue: notifications
spec:
  replicas: 1
  selector:
    matchLabels:
      app: anvilops-worker
      queue: notifications
  template:
    metadata:
      labels:
        app: anvilops-worker
        queue: notifications
    spec:
      serviceAccountName: anvilops-worker-sa
      nodeSelector:
        workload: application
      containers:
        - name: worker
          image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
          command:
            - celery
            - -A
            - app.worker.celery_app
            - worker
            - --loglevel=info
            - --concurrency=4
            - -Q
            - notifications
          envFrom:
            - secretRef:
                name: anvilops-secrets
          env:
            - name: SLACK_ENABLED
              value: "true"
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 1Gi
```

### 10.5 Celery Beat (Periodic Tasks)

Save as `k8s/beat-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvilops-celery-beat
  namespace: anvilops
  labels:
    app: anvilops-beat
spec:
  replicas: 1  # Must be exactly 1
  strategy:
    type: Recreate  # Prevent duplicate schedulers
  selector:
    matchLabels:
      app: anvilops-beat
  template:
    metadata:
      labels:
        app: anvilops-beat
    spec:
      serviceAccountName: anvilops-worker-sa
      nodeSelector:
        workload: application
      containers:
        - name: beat
          image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/anvilops-api:latest
          command:
            - celery
            - -A
            - app.worker.celery_app
            - beat
            - --loglevel=info
          envFrom:
            - secretRef:
                name: anvilops-secrets
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 250m
              memory: 512Mi
```

### 10.6 Ingress (ALB)

Save as `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: anvilops-ingress
  namespace: anvilops
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:<ACCOUNT_ID>:certificate/<CERT_ID>
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/wafv2-acl-arn: arn:aws:wafv2:us-east-1:<ACCOUNT_ID>:regional/webacl/<WAF_ACL_ID>
spec:
  rules:
    - host: anvilops.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: anvilops-api
                port:
                  number: 8000
          - path: /health
            pathType: Exact
            backend:
              service:
                name: anvilops-api
                port:
                  number: 8000
          - path: /docs
            pathType: Prefix
            backend:
              service:
                name: anvilops-api
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: anvilops-frontend
                port:
                  number: 3000
```

### 10.7 Apply All Manifests

```bash
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/beat-deployment.yaml
kubectl apply -f k8s/ingress.yaml

# Verify everything is running
kubectl get pods -n anvilops
kubectl get svc -n anvilops
kubectl get ingress -n anvilops
```

---

## 11. AWX Deployment

AWX provides Day-1 post-provisioning configuration via Ansible playbooks.

### 11.1 Install AWX Operator

```bash
# Install AWX Operator via Helm
helm repo add awx-operator https://ansible.github.io/awx-operator/
helm install awx-operator awx-operator/awx-operator \
  --namespace awx \
  --set AWX.enabled=true
```

### 11.2 Deploy AWX Instance

Save as `k8s/awx-instance.yaml`:

```yaml
apiVersion: awx.ansible.com/v1beta1
kind: AWX
metadata:
  name: awx
  namespace: awx
spec:
  replicas: 1
  admin_user: admin
  admin_password_secret: awx-admin-password
  postgres_configuration_secret: awx-postgres-config
  node_selector:
    workload: awx
  web_resource_requirements:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  task_resource_requirements:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  ee_resource_requirements:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi
```

```bash
# Create AWX secrets
kubectl create secret generic awx-admin-password \
  --namespace awx \
  --from-literal=password='<AWX_ADMIN_PASSWORD>'

# AWX can use its own PostgreSQL or share RDS (separate database recommended)
kubectl create secret generic awx-postgres-config \
  --namespace awx \
  --from-literal=host="$RDS_ENDPOINT" \
  --from-literal=port="5432" \
  --from-literal=database="awx" \
  --from-literal=username="awx" \
  --from-literal=password="<AWX_DB_PASSWORD>" \
  --from-literal=sslmode="require" \
  --from-literal=type="unmanaged"

# Deploy AWX
kubectl apply -f k8s/awx-instance.yaml

# Wait for AWX to be ready (5-10 minutes)
kubectl get pods -n awx -w
```

### 11.3 Configure AWX for AnvilOps

After AWX is running, configure it with the AnvilOps playbooks:

```bash
AWX_URL="http://$(kubectl get svc -n awx awx-service -o jsonpath='{.spec.clusterIP}')"

# Create organization
awx organizations create --name "AnvilOps" --description "AnvilOps Server Provisioning"

# Add project (Git repo with Ansible playbooks)
awx projects create \
  --name "AnvilOps Playbooks" \
  --organization "AnvilOps" \
  --scm-type git \
  --scm-url "https://github.com/jconover/anvilops.git" \
  --scm-branch main

# Create inventory (Dynamic AWS discovery)
awx inventories create \
  --name "AWS Dynamic" \
  --organization "AnvilOps"

awx inventory_sources create \
  --name "AWS EC2" \
  --inventory "AWS Dynamic" \
  --source ec2 \
  --source-vars '{"filters": "tag:ManagedBy=AnvilOps", "keyed_groups": [{"key": "tags.Environment", "prefix": "env"}]}'

# Create job templates for each playbook
for PLAYBOOK in linux-base windows-base domain-join install-software deploy-agents puppet-bootstrap; do
  awx job_templates create \
    --name "AnvilOps - ${PLAYBOOK}" \
    --project "AnvilOps Playbooks" \
    --playbook "ansible/playbooks/${PLAYBOOK}.yml" \
    --inventory "AWS Dynamic" \
    --ask-limit-on-launch true \
    --ask-variables-on-launch true
done
```

### 11.4 Update AnvilOps Configuration

```bash
# Update the Kubernetes secret with AWX credentials
kubectl create secret generic anvilops-secrets \
  --namespace anvilops \
  --from-literal=AWX_PASSWORD="<AWX_ADMIN_PASSWORD>" \
  --dry-run=client -o yaml | kubectl apply -f -

# Set AWX URL in API deployment env
# AWX_BASE_URL should be: http://awx-service.awx.svc.cluster.local:80
```

---

## 12. Puppet Enterprise

Puppet Enterprise provides Day-2+ continuous compliance enforcement and drift detection.

### 12.1 Launch Puppet Enterprise Server

Puppet Enterprise runs on a dedicated EC2 instance (not on EKS).

```bash
# Create Puppet server security group
PUPPET_SG=$(aws ec2 create-security-group \
  --group-name anvilops-puppet-sg \
  --description "Puppet Enterprise server" \
  --vpc-id $VPC_ID --query 'GroupId' --output text)

# Puppet ports
aws ec2 authorize-security-group-ingress --group-id $PUPPET_SG --protocol tcp --port 8140 --cidr 10.0.0.0/8    # Puppet agent
aws ec2 authorize-security-group-ingress --group-id $PUPPET_SG --protocol tcp --port 4433 --cidr 10.0.0.0/8    # Classifier
aws ec2 authorize-security-group-ingress --group-id $PUPPET_SG --protocol tcp --port 8081 --cidr 10.0.0.0/8    # PuppetDB
aws ec2 authorize-security-group-ingress --group-id $PUPPET_SG --protocol tcp --port 8143 --cidr 10.0.0.0/8    # Orchestrator
aws ec2 authorize-security-group-ingress --group-id $PUPPET_SG --protocol tcp --port 443 --source-group $EKS_SG # Console (API)
aws ec2 authorize-security-group-ingress --group-id $PUPPET_SG --protocol tcp --port 22 --cidr 10.0.0.0/8      # SSH

# Launch EC2 instance (m5.xlarge recommended for PE)
PUPPET_INSTANCE=$(aws ec2 run-instances \
  --image-id ami-0abcdef1234567890 \
  --instance-type m5.xlarge \
  --key-name anvilops-key \
  --security-group-ids $PUPPET_SG \
  --subnet-id $PRIV_SUB_10 \
  --iam-instance-profile Name=anvilops-puppet-profile \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3","Encrypted":true}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=anvilops-puppet},{Key=Environment,Value=production},{Key=ManagedBy,Value=AnvilOps}]' \
  --query 'Instances[0].InstanceId' --output text)

echo "Puppet Enterprise Instance: $PUPPET_INSTANCE"
aws ec2 wait instance-running --instance-ids $PUPPET_INSTANCE

PUPPET_IP=$(aws ec2 describe-instances --instance-ids $PUPPET_INSTANCE \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)
echo "Puppet IP: $PUPPET_IP"
```

### 12.2 Install Puppet Enterprise

SSH into the instance and install PE:

```bash
ssh ec2-user@$PUPPET_IP

# Download and install Puppet Enterprise (trial license — 10 nodes)
curl -O https://pm.puppet.com/puppet-enterprise/latest/puppet-enterprise-latest-el-8-x86_64.tar.gz
tar -xf puppet-enterprise-latest-el-8-x86_64.tar.gz
cd puppet-enterprise-*

# Create pe.conf
cat > pe.conf <<'EOF'
{
  "puppet_enterprise::puppet_master_host": "puppet.anvilops.internal",
  "console_admin_password": "CHANGE_ME_STRONG_PASSWORD",
  "puppet_enterprise::profile::master::r10k_remote": "https://github.com/jconover/anvilops.git",
  "puppet_enterprise::profile::master::r10k_basedir": "/etc/puppetlabs/code/environments",
  "puppet_enterprise::profile::master::code_manager_auto_configure": true
}
EOF

sudo ./puppet-enterprise-installer -c pe.conf -y
```

### 12.3 Configure Puppet for AnvilOps

```bash
# After PE installation completes:

# Generate an API token for AnvilOps backend
sudo puppet-access login --username admin --lifetime 1y
PUPPET_TOKEN=$(cat ~/.puppetlabs/token)
echo "Puppet API Token: $PUPPET_TOKEN"

# Deploy code from the AnvilOps repo
sudo puppet-code deploy production --wait

# Configure node groups matching AnvilOps roles
# AnvilOps creates these via the Classifier API:
# - AnvilOps Base (all nodes)
# - AnvilOps Web Server
# - AnvilOps App Server
# - AnvilOps DB Server
# - AnvilOps Dev Workstation
```

### 12.4 Route 53 Internal DNS

```bash
# Create private hosted zone for Puppet
PUPPET_ZONE_ID=$(aws route53 create-hosted-zone \
  --name anvilops.internal \
  --vpc VPCRegion=us-east-1,VPCId=$VPC_ID \
  --caller-reference "puppet-$(date +%s)" \
  --query 'HostedZone.Id' --output text)

# Create DNS record for Puppet server
aws route53 change-resource-record-sets \
  --hosted-zone-id $PUPPET_ZONE_ID \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"UPSERT\",
      \"ResourceRecordSet\": {
        \"Name\": \"puppet.anvilops.internal\",
        \"Type\": \"A\",
        \"TTL\": 300,
        \"ResourceRecords\": [{\"Value\": \"$PUPPET_IP\"}]
      }
    }]
  }"
```

### 12.5 Update AnvilOps Secrets

```bash
kubectl create secret generic anvilops-secrets \
  --namespace anvilops \
  --from-literal=PUPPET_API_TOKEN="$PUPPET_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 13. DNS & Load Balancing

### 13.1 ACM Certificate

```bash
# Request a public certificate for your domain
CERT_ARN=$(aws acm request-certificate \
  --domain-name anvilops.example.com \
  --validation-method DNS \
  --subject-alternative-names "*.anvilops.example.com" \
  --query 'CertificateArn' --output text)

echo "Certificate ARN: $CERT_ARN"
echo "Validate via DNS — add the CNAME records shown in:"
aws acm describe-certificate --certificate-arn $CERT_ARN \
  --query 'Certificate.DomainValidationOptions[*].ResourceRecord'

# Wait for validation
aws acm wait certificate-validated --certificate-arn $CERT_ARN
```

### 13.2 Route 53 Public Zone

```bash
# Create or use existing public hosted zone
PUBLIC_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name example.com \
  --query 'HostedZones[0].Id' --output text)

# After the ALB is created by the Ingress controller, create an alias record:
ALB_DNS=$(kubectl get ingress anvilops-ingress -n anvilops -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
ALB_ZONE=$(aws elbv2 describe-load-balancers --query "LoadBalancers[?DNSName=='$ALB_DNS'].CanonicalHostedZoneId" --output text)

aws route53 change-resource-record-sets \
  --hosted-zone-id $PUBLIC_ZONE_ID \
  --change-batch "{
    \"Changes\": [{
      \"Action\": \"UPSERT\",
      \"ResourceRecordSet\": {
        \"Name\": \"anvilops.example.com\",
        \"Type\": \"A\",
        \"AliasTarget\": {
          \"HostedZoneId\": \"$ALB_ZONE\",
          \"DNSName\": \"$ALB_DNS\",
          \"EvaluateTargetHealth\": true
        }
      }
    }]
  }"
```

### 13.3 WAF v2

```bash
# Create WAF Web ACL
WAF_ACL_ID=$(aws wafv2 create-web-acl \
  --name anvilops-waf \
  --scope REGIONAL \
  --default-action Allow={} \
  --rules '[
    {
      "Name": "AWSManagedRulesCommonRuleSet",
      "Priority": 1,
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesCommonRuleSet"
        }
      },
      "OverrideAction": {"None": {}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "CommonRuleSet"
      }
    },
    {
      "Name": "AWSManagedRulesSQLiRuleSet",
      "Priority": 2,
      "Statement": {
        "ManagedRuleGroupStatement": {
          "VendorName": "AWS",
          "Name": "AWSManagedRulesSQLiRuleSet"
        }
      },
      "OverrideAction": {"None": {}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "SQLiRuleSet"
      }
    },
    {
      "Name": "RateLimitRule",
      "Priority": 3,
      "Statement": {
        "RateBasedStatement": {
          "Limit": 2000,
          "AggregateKeyType": "IP"
        }
      },
      "Action": {"Block": {}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "RateLimit"
      }
    }
  ]' \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=anvilops-waf \
  --query 'Summary.Id' --output text)

echo "WAF ACL ID: $WAF_ACL_ID"
```

---

## 14. CI/CD Pipeline

### 14.1 GitHub Actions Workflow

Save as `.github/workflows/deploy.yml`:

```yaml
name: Build & Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  EKS_CLUSTER: anvilops
  ECR_REGISTRY: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com

permissions:
  id-token: write
  contents: read

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: anvilops
          POSTGRES_PASSWORD: anvilops
          POSTGRES_DB: anvilops
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install backend dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx ruff

      - name: Lint
        run: |
          cd backend
          ruff check .

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://anvilops:anvilops@localhost:5432/anvilops
          REDIS_URL: redis://localhost:6379/0
        run: |
          cd backend
          pytest -v

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Frontend lint
        run: |
          cd frontend
          npm ci
          npm run lint

  build-and-push:
    name: Build & Push Images
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - name: api
            context: ./backend
            dockerfile: ./backend/Dockerfile
            repository: anvilops-api
          - name: frontend
            context: ./frontend
            dockerfile: ./frontend/Dockerfile
            repository: anvilops-frontend
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ${{ matrix.context }}
          file: ${{ matrix.dockerfile }}
          push: true
          tags: |
            ${{ env.ECR_REGISTRY }}/${{ matrix.repository }}:${{ github.sha }}
            ${{ env.ECR_REGISTRY }}/${{ matrix.repository }}:latest

  deploy:
    name: Deploy to EKS
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name ${{ env.EKS_CLUSTER }} --region ${{ env.AWS_REGION }}

      - name: Deploy to EKS
        run: |
          IMAGE_TAG=${{ github.sha }}

          # Update API deployment
          kubectl set image deployment/anvilops-api \
            api=${{ env.ECR_REGISTRY }}/anvilops-api:${IMAGE_TAG} \
            -n anvilops

          # Update Frontend deployment
          kubectl set image deployment/anvilops-frontend \
            frontend=${{ env.ECR_REGISTRY }}/anvilops-frontend:${IMAGE_TAG} \
            -n anvilops

          # Update worker deployments
          for DEPLOY in anvilops-worker-default anvilops-worker-terraform anvilops-worker-notifications anvilops-celery-beat; do
            kubectl set image deployment/${DEPLOY} \
              worker=${{ env.ECR_REGISTRY }}/anvilops-api:${IMAGE_TAG} \
              -n anvilops 2>/dev/null || true
          done

          # Run migrations
          kubectl exec deploy/anvilops-api -n anvilops -- alembic upgrade head

          # Wait for rollout
          kubectl rollout status deployment/anvilops-api -n anvilops --timeout=300s
          kubectl rollout status deployment/anvilops-frontend -n anvilops --timeout=300s

      - name: Verify deployment
        run: |
          ALB_DNS=$(kubectl get ingress anvilops-ingress -n anvilops -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
          curl -sf "https://${ALB_DNS}/health" || echo "Health check pending (DNS propagation may take a few minutes)"
```

### 14.2 GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID |
| `AWS_DEPLOY_ROLE_ARN` | ARN of the IAM role for GitHub Actions (OIDC) |

### 14.3 GitHub Actions OIDC Integration

```bash
# Create OIDC identity provider for GitHub Actions
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create deploy role
aws iam create-role \
  --role-name github-actions-anvilops-deploy \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"},
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:jconover/anvilops:ref:refs/heads/main"
        }
      }
    }]
  }'

# Attach required policies
aws iam attach-role-policy --role-name github-actions-anvilops-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
aws iam attach-role-policy --role-name github-actions-anvilops-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSClusterPolicy
```

---

## 15. Observability & Monitoring

### 15.1 CloudWatch Log Groups

```bash
# Create log groups for each component
for LOG_GROUP in \
  /anvilops/api \
  /anvilops/worker \
  /anvilops/frontend \
  /anvilops/celery-beat \
  /ecs/anvilops-terraform; do
  aws logs create-log-group --log-group-name $LOG_GROUP
  aws logs put-retention-policy --log-group-name $LOG_GROUP --retention-in-days 30
done
```

### 15.2 Prometheus & Grafana on EKS

```bash
# Install Prometheus stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.adminPassword="CHANGE_ME" \
  --set grafana.ingress.enabled=true \
  --set grafana.ingress.annotations."kubernetes\.io/ingress\.class"=alb \
  --set grafana.ingress.hosts[0]=grafana.anvilops.example.com \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=gp2 \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi
```

### 15.3 FastAPI Custom Metrics

Add a Prometheus metrics endpoint to the FastAPI app for scraping:

```python
# Expose at /metrics — Prometheus scrapes this
# Key metrics to track:
# - anvilops_server_requests_total (counter, by status)
# - anvilops_build_duration_seconds (histogram)
# - anvilops_active_builds (gauge)
# - anvilops_terraform_runs_total (counter, by result)
# - anvilops_awx_jobs_total (counter, by result)
# - anvilops_puppet_enrollments_total (counter, by result)
```

### 15.4 CloudWatch Alarms

```bash
# RDS CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name anvilops-rds-cpu-high \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=DBInstanceIdentifier,Value=anvilops-db \
  --evaluation-periods 3 \
  --alarm-actions "arn:aws:sns:us-east-1:<ACCOUNT_ID>:anvilops-alerts"

# RDS free storage alarm
aws cloudwatch put-metric-alarm \
  --alarm-name anvilops-rds-storage-low \
  --metric-name FreeStorageSpace \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 10737418240 \
  --comparison-operator LessThanThreshold \
  --dimensions Name=DBInstanceIdentifier,Value=anvilops-db \
  --evaluation-periods 2 \
  --alarm-actions "arn:aws:sns:us-east-1:<ACCOUNT_ID>:anvilops-alerts"

# Redis CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name anvilops-redis-cpu-high \
  --metric-name CPUUtilization \
  --namespace AWS/ElastiCache \
  --statistic Average \
  --period 300 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ReplicationGroupId,Value=anvilops-redis \
  --evaluation-periods 3 \
  --alarm-actions "arn:aws:sns:us-east-1:<ACCOUNT_ID>:anvilops-alerts"

# EKS pod restart alarm (via Container Insights)
aws cloudwatch put-metric-alarm \
  --alarm-name anvilops-pod-restarts \
  --metric-name pod_number_of_container_restarts \
  --namespace ContainerInsights \
  --statistic Maximum \
  --period 300 \
  --threshold 3 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ClusterName,Value=anvilops Name=Namespace,Value=anvilops \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:us-east-1:<ACCOUNT_ID>:anvilops-alerts"
```

### 15.5 SNS Alert Topic

```bash
# Create SNS topic for alerts
aws sns create-topic --name anvilops-alerts

# Subscribe email
aws sns subscribe \
  --topic-arn "arn:aws:sns:us-east-1:<ACCOUNT_ID>:anvilops-alerts" \
  --protocol email \
  --notification-endpoint ops-team@example.com

# Subscribe Slack (via AWS Chatbot or Lambda)
# See: https://docs.aws.amazon.com/chatbot/latest/adminguide/slack-setup.html
```

### 15.6 Container Insights

```bash
# Enable Container Insights on EKS
aws eks update-cluster-config \
  --name anvilops \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'

# Install CloudWatch agent
helm repo add amazon-cloudwatch https://aws.github.io/eks-charts
helm install cloudwatch-agent amazon-cloudwatch/aws-cloudwatch-observability \
  --namespace amazon-cloudwatch --create-namespace \
  --set clusterName=anvilops \
  --set region=us-east-1
```

---

## 16. Testing & Validation

### 16.1 Smoke Tests

Run these after deployment to verify all components are working:

```bash
# 1. API health check
curl -sf https://anvilops.example.com/health
# Expected: {"status": "healthy", "service": "anvilops-api"}

# 2. API docs accessible
curl -sf https://anvilops.example.com/docs -o /dev/null && echo "Swagger UI OK"

# 3. List regions
curl -sf https://anvilops.example.com/api/v1/regions/ | jq '.regions | length'
# Expected: 2 (us-east-1, us-west-2)

# 4. List templates
curl -sf https://anvilops.example.com/api/v1/templates/ | jq '. | length'
# Expected: 6

# 5. Cost estimation
curl -sf -X POST https://anvilops.example.com/api/v1/costs/estimate \
  -H "Content-Type: application/json" \
  -d '{"instance_size":"small","os_type":"amazon_linux_2023","region":"us-east-1","additional_storage":[]}' | jq .
# Expected: cost estimate response

# 6. Frontend loads
curl -sf https://anvilops.example.com/ -o /dev/null && echo "Frontend OK"

# 7. Database connectivity (from API pod)
kubectl exec deploy/anvilops-api -n anvilops -- python -c "
from app.core.config import settings
print(f'DB URL configured: {settings.DATABASE_URL[:30]}...')
"

# 8. Redis connectivity (from worker pod)
kubectl exec deploy/anvilops-worker-default -n anvilops -- python -c "
import redis
r = redis.from_url('$REDIS_URL')
print(f'Redis PING: {r.ping()}')
"

# 9. Celery workers registered
kubectl exec deploy/anvilops-worker-default -n anvilops -- celery -A app.worker.celery_app inspect active_queues

# 10. AWX reachable
kubectl exec deploy/anvilops-api -n anvilops -- python -c "
import httpx
r = httpx.get('http://awx-service.awx.svc.cluster.local/api/v2/ping/')
print(f'AWX: {r.status_code}')
"
```

### 16.2 End-to-End Server Build Test

```bash
# Create a dev server request (will actually provision infrastructure)
curl -X POST https://anvilops.example.com/api/v1/servers/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "environment": "dev",
    "os_type": "amazon_linux_2023",
    "instance_size": "small",
    "region": "us-east-1",
    "vpc_id": "<DEV_VPC_ID>",
    "subnet_id": "<DEV_SUBNET_ID>"
  }'

# Monitor the build pipeline
SERVER_ID="<from response>"
watch -n 5 "curl -sf https://anvilops.example.com/api/v1/servers/$SERVER_ID | jq '{status, server_name, instance_id, private_ip}'"

# Expected progression:
# pending → approved (dev auto-approves) → provisioning → configuring → validating → ready

# Clean up: decommission the test server
curl -X POST "https://anvilops.example.com/api/v1/servers/$SERVER_ID/decommission"
```

### 16.3 Checklist

| Check | Command | Expected |
|-------|---------|----------|
| API responds | `curl /health` | `{"status":"healthy"}` |
| DB connected | `kubectl exec ... -- alembic current` | Migration hash |
| Redis connected | `kubectl exec ... -- redis-cli ping` | PONG |
| Workers registered | `celery inspect active_queues` | 3 queues listed |
| Frontend loads | Browser test | Dashboard renders |
| VPCs discovered | `GET /api/v1/regions/us-east-1/vpcs` | VPC list |
| Templates seeded | `GET /api/v1/templates/` | 6 templates |
| AWX reachable | AWX ping API | 200 OK |
| Puppet reachable | Puppet status API | 200 OK |
| SSL valid | `curl -v https://...` | Valid certificate |
| WAF active | AWS Console | Rules enforcing |
| Logs flowing | CloudWatch | Recent entries |
| Alarms configured | `aws cloudwatch describe-alarms` | 4+ alarms |

---

## 17. Operational Runbook

### 17.1 Scaling

```bash
# Scale API pods
kubectl scale deployment/anvilops-api -n anvilops --replicas=5

# Scale Celery workers (for high build volume)
kubectl scale deployment/anvilops-worker-default -n anvilops --replicas=4
kubectl scale deployment/anvilops-worker-terraform -n anvilops --replicas=4

# Scale EKS nodes (auto-scaling handles this, but manual override)
eksctl scale nodegroup --cluster anvilops --name app-nodes --nodes 5
```

### 17.2 Database Operations

```bash
# Connect to RDS (via port-forward through a bastion or EKS pod)
kubectl run psql-client --rm -it --namespace anvilops \
  --image postgres:16-alpine \
  -- psql "postgresql://anvilops:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/anvilops"

# Run migrations
kubectl exec deploy/anvilops-api -n anvilops -- alembic upgrade head

# Create manual RDS snapshot
aws rds create-db-snapshot \
  --db-instance-identifier anvilops-db \
  --db-snapshot-identifier "anvilops-manual-$(date +%Y%m%d-%H%M%S)"
```

### 17.3 Rolling Back

```bash
# Rollback API deployment
kubectl rollout undo deployment/anvilops-api -n anvilops

# Rollback to specific revision
kubectl rollout history deployment/anvilops-api -n anvilops
kubectl rollout undo deployment/anvilops-api -n anvilops --to-revision=3

# Rollback database migration
kubectl exec deploy/anvilops-api -n anvilops -- alembic downgrade -1
```

### 17.4 Log Access

```bash
# API logs
kubectl logs -n anvilops deploy/anvilops-api --tail=100 -f

# Worker logs (all queues)
kubectl logs -n anvilops -l app=anvilops-worker --tail=100 -f

# Specific Terraform task logs
aws logs get-log-events \
  --log-group-name /ecs/anvilops-terraform \
  --log-stream-name "terraform/<task-id>"

# AWX logs
kubectl logs -n awx deploy/awx-task --tail=100 -f
```

### 17.5 Emergency Procedures

**Celery queue backed up:**
```bash
# Check queue depth
kubectl exec deploy/anvilops-worker-default -n anvilops -- \
  celery -A app.worker.celery_app inspect reserved

# Purge a specific queue (destructive — pending tasks are lost)
kubectl exec deploy/anvilops-worker-default -n anvilops -- \
  celery -A app.worker.celery_app purge -Q notifications -f
```

**Stuck Terraform state lock:**
```bash
# List locks
aws dynamodb scan --table-name anvilops-terraform-locks

# Force unlock (use the LockID from the scan)
aws dynamodb delete-item --table-name anvilops-terraform-locks \
  --key '{"LockID": {"S": "<LOCK_ID>"}}'
```

**RDS failover (Multi-AZ):**
```bash
# Force failover to standby
aws rds reboot-db-instance --db-instance-identifier anvilops-db --force-failover
```

---

## 18. Cost Estimate

Approximate monthly costs for the production deployment:

| Resource | Specification | Monthly Cost |
|----------|--------------|-------------|
| EKS Cluster | Control plane | $73 |
| EKS Nodes (app) | 3x t3.xlarge | $373 |
| EKS Nodes (AWX) | 2x m5.xlarge | $280 |
| RDS PostgreSQL | db.r6g.large Multi-AZ | $380 |
| ElastiCache Redis | cache.r6g.large (2 nodes) | $360 |
| NAT Gateways | 2x (data transfer varies) | $65+ |
| ALB | 1x + data transfer | $25+ |
| S3 (TF state) | Minimal storage | $1 |
| S3 (TF lock files) | Minimal | $0 |
| ECR | Image storage | $5 |
| Route 53 | Hosted zones + queries | $2 |
| CloudWatch | Logs + metrics + alarms | $30 |
| Secrets Manager | 10 secrets | $4 |
| ACM | Free (public certs) | $0 |
| Puppet Enterprise EC2 | m5.xlarge | $140 |
| **Total** | | **~$1,740/mo** |

> **Cost optimization tips:**
> - Use Reserved Instances or Savings Plans for 30-50% savings on steady-state compute
> - Use Spot Instances for Celery workers (with graceful handling)
> - Use `FARGATE_SPOT` for Terraform runner tasks (already configured)
> - Start with smaller instances (t3.large) and scale up based on actual usage
> - Consider single-AZ for dev/staging environments

---

## Appendix: Environment Variables for Production

```env
# Core
DATABASE_URL=postgresql+asyncpg://anvilops:<PASSWORD>@<RDS_ENDPOINT>:5432/anvilops
REDIS_URL=rediss://<ELASTICACHE_ENDPOINT>:6379/0
DEBUG=false
PROJECT_NAME=AnvilOps

# AWS
AWS_DEFAULT_REGION=us-east-1
TERRAFORM_WORK_DIR=/tmp/terraform

# AWX
AWX_BASE_URL=http://awx-service.awx.svc.cluster.local:80
AWX_USERNAME=admin
AWX_PASSWORD=<FROM_SECRETS_MANAGER>
AWX_VERIFY_SSL=false
AWX_JOB_TIMEOUT=600
AWX_POLL_INTERVAL=10

# Puppet
PUPPET_BASE_URL=https://puppet.anvilops.internal
PUPPET_API_TOKEN=<FROM_SECRETS_MANAGER>
PUPPET_VERIFY_SSL=true
PUPPET_CERTNAME_DOMAIN=anvilops.internal

# Slack
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=<FROM_SECRETS_MANAGER>
SLACK_SIGNING_SECRET=<FROM_SECRETS_MANAGER>
SLACK_CHANNEL=#anvilops-builds
SLACK_APP_URL=https://anvilops.example.com

# Cognito
COGNITO_USER_POOL_ID=<POOL_ID>
COGNITO_CLIENT_ID=<CLIENT_ID>
COGNITO_REGION=us-east-1

# ServiceNow (optional)
SERVICENOW_ENABLED=false
SERVICENOW_INSTANCE_URL=
SERVICENOW_USERNAME=
SERVICENOW_PASSWORD=
```
