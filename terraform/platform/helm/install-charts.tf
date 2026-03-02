# =============================================================================
# AnvilOps EKS Add-Ons — Helm Chart Installation
# =============================================================================

terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }
}

# -----------------------------------------------------------------------------
# Providers
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.region
}

# Fetch cluster connection details automatically — no manual token passing.
data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "this" {
  name = var.cluster_name
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "kubectl" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
  load_config_file       = false
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the EKS cluster is running."
  type        = string
}

variable "domain" {
  description = "DNS domain managed by External DNS."
  type        = string
}

variable "alb_controller_role_arn" {
  description = "IAM role ARN for the AWS Load Balancer Controller (IRSA)."
  type        = string
}

variable "external_dns_role_arn" {
  description = "IAM role ARN for External DNS (IRSA)."
  type        = string
}

variable "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler (IRSA)."
  type        = string
}

variable "redis_endpoint" {
  description = "Redis endpoint for KEDA Celery autoscaling."
  type        = string
}

# -----------------------------------------------------------------------------
# AWS Load Balancer Controller
# -----------------------------------------------------------------------------

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "1.12.0"
  namespace  = "kube-system"

  values = [
    templatefile("${path.module}/aws-load-balancer-controller-values.yaml", {
      cluster_name            = var.cluster_name
      alb_controller_role_arn = var.alb_controller_role_arn
      region                  = var.region
      vpc_id                  = var.vpc_id
    })
  ]

  timeout = 600
  wait    = true
}

# -----------------------------------------------------------------------------
# External Secrets Operator
# -----------------------------------------------------------------------------

resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  version          = "0.14.3"
  namespace        = "external-secrets"
  create_namespace = true

  values = [file("${path.module}/external-secrets-values.yaml")]

  timeout    = 600
  wait       = true
  atomic     = true
  depends_on = [helm_release.aws_load_balancer_controller]
}

# -----------------------------------------------------------------------------
# External DNS
# -----------------------------------------------------------------------------

resource "helm_release" "external_dns" {
  name             = "external-dns"
  repository       = "https://kubernetes-sigs.github.io/external-dns"
  chart            = "external-dns"
  version          = "1.16.1"
  namespace        = "external-dns"
  create_namespace = true

  values = [
    templatefile("${path.module}/external-dns-values.yaml", {
      external_dns_role_arn = var.external_dns_role_arn
      region                = var.region
      domain                = var.domain
      cluster_name          = var.cluster_name
    })
  ]

  timeout    = 600
  wait       = true
  depends_on = [helm_release.aws_load_balancer_controller]
}

# -----------------------------------------------------------------------------
# Metrics Server
# -----------------------------------------------------------------------------

resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server"
  chart      = "metrics-server"
  version    = "3.13.0"
  namespace  = "kube-system"

  values = [file("${path.module}/metrics-server-values.yaml")]

  timeout = 300
  wait    = true
}

# -----------------------------------------------------------------------------
# Cluster Autoscaler
# -----------------------------------------------------------------------------

resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  version    = "9.44.0"
  namespace  = "kube-system"

  values = [
    templatefile("${path.module}/cluster-autoscaler-values.yaml", {
      cluster_name                = var.cluster_name
      region                      = var.region
      cluster_autoscaler_role_arn = var.cluster_autoscaler_role_arn
    })
  ]

  timeout    = 300
  wait       = true
  depends_on = [helm_release.metrics_server]
}

# -----------------------------------------------------------------------------
# KEDA
# -----------------------------------------------------------------------------

resource "helm_release" "keda" {
  name             = "keda"
  repository       = "https://kedacore.github.io/charts"
  chart            = "keda"
  version          = "2.17.0"
  namespace        = "keda"
  create_namespace = true

  values = [file("${path.module}/keda-values.yaml")]

  timeout    = 600
  wait       = true
  atomic     = true
  depends_on = [helm_release.aws_load_balancer_controller]
}

# -----------------------------------------------------------------------------
# Application Namespace
# -----------------------------------------------------------------------------

resource "kubectl_manifest" "anvilops_namespace" {
  yaml_body = <<-YAML
    apiVersion: v1
    kind: Namespace
    metadata:
      name: anvilops
      labels:
        app.kubernetes.io/part-of: anvilops
  YAML
}

# -----------------------------------------------------------------------------
# KEDA ScaledObject for Celery Workers
# -----------------------------------------------------------------------------

resource "kubectl_manifest" "keda_celery_scaledobject" {
  yaml_body = templatefile("${path.module}/keda-celery-scaledobject.yaml", {
    redis_endpoint = var.redis_endpoint
  })

  depends_on = [helm_release.keda, kubectl_manifest.anvilops_namespace]
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "installed_charts" {
  description = "Map of installed Helm chart names and versions."
  value = {
    aws_load_balancer_controller = "${helm_release.aws_load_balancer_controller.chart}:${helm_release.aws_load_balancer_controller.version}"
    external_secrets             = "${helm_release.external_secrets.chart}:${helm_release.external_secrets.version}"
    external_dns                 = "${helm_release.external_dns.chart}:${helm_release.external_dns.version}"
    metrics_server               = "${helm_release.metrics_server.chart}:${helm_release.metrics_server.version}"
    cluster_autoscaler           = "${helm_release.cluster_autoscaler.chart}:${helm_release.cluster_autoscaler.version}"
    keda                         = "${helm_release.keda.chart}:${helm_release.keda.version}"
  }
}
