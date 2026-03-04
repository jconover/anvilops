# =============================================================================
# AnvilOps EKS Add-Ons — Helm Chart Installation
# =============================================================================

# Map non-HashiCorp providers so Terraform resolves the correct source.
# Version constraints and provider configuration are inherited from the parent.
terraform {
  required_providers {
    kubectl = {
      source = "gavinbunney/kubectl"
    }
  }
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

variable "rds_endpoint" {
  description = "RDS endpoint for AWX PostgreSQL connection."
  type        = string
  default     = ""
}

variable "awx_git_repo_url" {
  description = "Git repository URL for AWX project sync."
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Project name for resource naming."
  type        = string
  default     = "anvilops"
}

variable "grafana_admin_password" {
  description = "Grafana admin password for kube-prometheus-stack."
  type        = string
  default     = "admin"
  sensitive   = true
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
# AWX Operator
# -----------------------------------------------------------------------------

resource "random_password" "awx_admin" {
  length           = 24
  special          = true
  override_special = "!@#$%^&*()-_=+[]{}:?"
}

resource "random_password" "awx_db" {
  length           = 24
  special          = true
  override_special = "!@#$%^&*()-_=+[]{}:?"
}

resource "helm_release" "awx_operator" {
  name             = "awx-operator"
  repository       = "https://ansible-community.github.io/awx-operator-helm/"
  chart            = "awx-operator"
  version          = "2.19.1"
  namespace        = "awx"
  create_namespace = true

  values = [file("${path.module}/awx-operator-values.yaml")]

  timeout    = 600
  wait       = true
  depends_on = [helm_release.aws_load_balancer_controller]
}

resource "kubectl_manifest" "awx_admin_password_secret" {
  yaml_body = <<-YAML
    apiVersion: v1
    kind: Secret
    metadata:
      name: awx-admin-password
      namespace: awx
    type: Opaque
    stringData:
      password: "${random_password.awx_admin.result}"
  YAML

  depends_on = [helm_release.awx_operator]
}

resource "kubectl_manifest" "awx_postgres_config_secret" {
  yaml_body = <<-YAML
    apiVersion: v1
    kind: Secret
    metadata:
      name: awx-postgres-configuration
      namespace: awx
    type: Opaque
    stringData:
      host: "${var.rds_endpoint}"
      port: "5432"
      database: "awx"
      username: "awx"
      password: "${random_password.awx_db.result}"
      type: "unmanaged"
      sslmode: "require"
  YAML

  depends_on = [helm_release.awx_operator]
}

resource "kubectl_manifest" "awx_instance" {
  yaml_body = templatefile("${path.module}/awx-instance.yaml", {
    awx_admin_password_secret_name  = "awx-admin-password"
    awx_postgres_config_secret_name = "awx-postgres-configuration"
  })

  depends_on = [
    helm_release.awx_operator,
    kubectl_manifest.awx_admin_password_secret,
    kubectl_manifest.awx_postgres_config_secret,
  ]
}

# Store AWX credentials in Secrets Manager (feeds the ExternalSecret in anvilops namespace)
resource "aws_secretsmanager_secret" "awx" {
  name                    = "anvilops/awx"
  description             = "AWX credentials for AnvilOps integration"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "awx" {
  secret_id = aws_secretsmanager_secret.awx.id
  secret_string = jsonencode({
    url      = "http://awx-service.awx.svc.cluster.local"
    username = "admin"
    password = random_password.awx_admin.result
  })
}

resource "kubectl_manifest" "awx_config_job" {
  yaml_body = templatefile("${path.module}/awx-config-job.yaml", {
    awx_admin_password     = random_password.awx_admin.result
    awx_git_repo_url       = var.awx_git_repo_url
    project_name           = var.project_name
    grafana_admin_password = var.grafana_admin_password
  })

  depends_on = [kubectl_manifest.awx_instance]
}

# -----------------------------------------------------------------------------
# Kube Prometheus Stack
# -----------------------------------------------------------------------------

resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "67.4.0"
  namespace        = "monitoring"
  create_namespace = true

  values = [
    templatefile("${path.module}/kube-prometheus-stack-values.yaml", {
      grafana_admin_password = var.grafana_admin_password
    })
  ]

  timeout    = 900
  wait       = true
  atomic     = true
  depends_on = [helm_release.aws_load_balancer_controller]
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
    awx_operator                 = "${helm_release.awx_operator.chart}:${helm_release.awx_operator.version}"
    kube_prometheus_stack        = "${helm_release.kube_prometheus_stack.chart}:${helm_release.kube_prometheus_stack.version}"
  }
}
