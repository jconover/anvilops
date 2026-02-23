# =============================================================================
# AnvilOps EKS Add-Ons — Helm Chart Installation
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
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
# Providers — use explicit config when variables are provided, otherwise
# fall back to the local kubeconfig (set by `aws eks update-kubeconfig`).
# -----------------------------------------------------------------------------

provider "helm" {
  kubernetes {
    host                   = var.cluster_endpoint != "" ? var.cluster_endpoint : null
    cluster_ca_certificate = var.cluster_ca_certificate != "" ? base64decode(var.cluster_ca_certificate) : null
    token                  = var.cluster_token != "" ? var.cluster_token : null

    # Falls back to ~/.kube/config when the above are null
    config_path = var.cluster_endpoint == "" ? "~/.kube/config" : null
  }
}

provider "kubectl" {
  host                   = var.cluster_endpoint != "" ? var.cluster_endpoint : null
  cluster_ca_certificate = var.cluster_ca_certificate != "" ? base64decode(var.cluster_ca_certificate) : null
  token                  = var.cluster_token != "" ? var.cluster_token : null
  load_config_file       = var.cluster_endpoint == "" ? true : false
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "cluster_endpoint" {
  description = "EKS cluster API endpoint URL. Leave empty to use local kubeconfig."
  type        = string
  default     = ""
}

variable "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the EKS cluster. Leave empty to use local kubeconfig."
  type        = string
  default     = ""
}

variable "cluster_token" {
  description = "Authentication token for the EKS cluster. Leave empty to use local kubeconfig."
  type        = string
  sensitive   = true
  default     = ""
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
  version    = "1.7.2"
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
  version          = "0.9.13"
  namespace        = "external-secrets"
  create_namespace = true

  values = [file("${path.module}/external-secrets-values.yaml")]

  timeout = 600
  wait    = true
}

# -----------------------------------------------------------------------------
# External DNS
# -----------------------------------------------------------------------------

resource "helm_release" "external_dns" {
  name             = "external-dns"
  repository       = "https://kubernetes-sigs.github.io/external-dns"
  chart            = "external-dns"
  version          = "1.14.3"
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

  timeout = 600
  wait    = true
}

# -----------------------------------------------------------------------------
# Metrics Server
# -----------------------------------------------------------------------------

resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server"
  chart      = "metrics-server"
  version    = "3.12.0"
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
  version    = "9.35.0"
  namespace  = "kube-system"

  values = [
    templatefile("${path.module}/cluster-autoscaler-values.yaml", {
      cluster_name               = var.cluster_name
      region                     = var.region
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
  version          = "2.13.1"
  namespace        = "keda"
  create_namespace = true

  values = [file("${path.module}/keda-values.yaml")]

  timeout = 600
  wait    = true
}

# -----------------------------------------------------------------------------
# KEDA ScaledObject for Celery Workers
# -----------------------------------------------------------------------------

resource "kubectl_manifest" "keda_celery_scaledobject" {
  yaml_body = templatefile("${path.module}/keda-celery-scaledobject.yaml", {
    redis_endpoint = var.redis_endpoint
  })

  depends_on = [helm_release.keda]
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
