# =============================================================================
# AnvilOps EKS Cluster Module
# =============================================================================
# EKS cluster running AnvilOps API, Celery workers, AWX, and supporting
# services. Includes KMS envelope encryption, IRSA via OIDC, managed node
# group with AL2023, and all core EKS add-ons.
# =============================================================================

locals {
  cluster_name = "${var.project_name}-${var.environment}"
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Fetch latest compatible add-on versions
data "aws_eks_addon_version" "vpc_cni" {
  addon_name         = "vpc-cni"
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

data "aws_eks_addon_version" "coredns" {
  addon_name         = "coredns"
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

data "aws_eks_addon_version" "kube_proxy" {
  addon_name         = "kube-proxy"
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

data "aws_eks_addon_version" "ebs_csi" {
  addon_name         = "aws-ebs-csi-driver"
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

data "aws_eks_addon_version" "cloudwatch_observability" {
  addon_name         = "amazon-cloudwatch-observability"
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

# TLS certificate for OIDC provider thumbprint
data "tls_certificate" "eks" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

# -----------------------------------------------------------------------------
# KMS Key — envelope encryption for Kubernetes secrets
# -----------------------------------------------------------------------------

resource "aws_kms_key" "eks" {
  description             = "KMS key for EKS secrets encryption - ${local.cluster_name}"
  deletion_window_in_days = 14
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_key_policy.json

  tags = merge(var.tags, { Name = "${local.cluster_name}-eks-secrets" })
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${local.cluster_name}-eks-secrets"
  target_key_id = aws_kms_key.eks.key_id
}

data "aws_iam_policy_document" "kms_key_policy" {
  statement {
    sid    = "EnableRootAccountAccess"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowEKSClusterRole"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.cluster.arn]
    }
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
      "kms:CreateGrant",
      "kms:ListGrants",
      "kms:RevokeGrant",
    ]
    resources = ["*"]
  }
}

# -----------------------------------------------------------------------------
# IAM Role — EKS Cluster (control plane)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "cluster_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${local.cluster_name}-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.cluster_assume_role.json
  tags               = merge(var.tags, { Name = "${local.cluster_name}-cluster-role" })
}

resource "aws_iam_role_policy_attachment" "cluster_eks_policy" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role_policy_attachment" "cluster_vpc_resource_controller" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSVPCResourceController"
}

# -----------------------------------------------------------------------------
# EKS Cluster
# -----------------------------------------------------------------------------

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    security_group_ids      = [var.eks_security_group_id]
  }

  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler",
  ]

  tags = merge(var.tags, { Name = local.cluster_name })

  depends_on = [
    aws_iam_role_policy_attachment.cluster_eks_policy,
    aws_iam_role_policy_attachment.cluster_vpc_resource_controller,
  ]
}

# -----------------------------------------------------------------------------
# Cluster Access — grant the deployer (caller) admin access
# -----------------------------------------------------------------------------

resource "aws_eks_access_entry" "deployer" {
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = data.aws_caller_identity.current.arn
  type          = "STANDARD"

  tags = merge(var.tags, { Name = "${local.cluster_name}-deployer-access" })
}

resource "aws_eks_access_policy_association" "deployer" {
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = aws_eks_access_entry.deployer.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# -----------------------------------------------------------------------------
# OIDC Provider — enables IRSA
# -----------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]

  tags = merge(var.tags, { Name = "${local.cluster_name}-oidc" })
}

# -----------------------------------------------------------------------------
# IAM Role — Managed Node Group
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "node_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "node_group" {
  name               = "${local.cluster_name}-node-role"
  assume_role_policy = data.aws_iam_policy_document.node_assume_role.json
  tags               = merge(var.tags, { Name = "${local.cluster_name}-node-role" })
}

resource "aws_iam_role_policy_attachment" "node_worker_policy" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_cni_policy" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "node_ecr_readonly" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "node_ssm" {
  role       = aws_iam_role.node_group.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# -----------------------------------------------------------------------------
# EKS Managed Node Group
# -----------------------------------------------------------------------------

resource "aws_eks_node_group" "workers" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-workers"
  node_role_arn   = aws_iam_role.node_group.arn
  subnet_ids      = var.private_subnet_ids

  instance_types = var.node_instance_types
  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = "ON_DEMAND"
  disk_size      = 50

  scaling_config {
    min_size     = var.node_min_size
    max_size     = var.node_max_size
    desired_size = var.node_desired_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    role        = "worker"
    environment = var.environment
  }

  tags = merge(var.tags, { Name = "${local.cluster_name}-workers" })

  depends_on = [
    aws_iam_role_policy_attachment.node_worker_policy,
    aws_iam_role_policy_attachment.node_cni_policy,
    aws_iam_role_policy_attachment.node_ecr_readonly,
    aws_iam_role_policy_attachment.node_ssm,
  ]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}

# -----------------------------------------------------------------------------
# IAM Role — EBS CSI Driver (IRSA)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "ebs_csi_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${local.cluster_name}-ebs-csi-role"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume_role.json
  tags               = merge(var.tags, { Name = "${local.cluster_name}-ebs-csi-role" })
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# -----------------------------------------------------------------------------
# IAM Role — CloudWatch Observability (IRSA)
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "cloudwatch_observability_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}:sub"
      values   = ["system:serviceaccount:amazon-cloudwatch:cloudwatch-agent"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cloudwatch_observability" {
  name               = "${local.cluster_name}-cw-observability-role"
  assume_role_policy = data.aws_iam_policy_document.cloudwatch_observability_assume_role.json
  tags               = merge(var.tags, { Name = "${local.cluster_name}-cw-observability-role" })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_observability_agent" {
  role       = aws_iam_role.cloudwatch_observability.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_observability_xray" {
  role       = aws_iam_role.cloudwatch_observability.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AWSXrayWriteOnlyAccess"
}

# -----------------------------------------------------------------------------
# EKS Add-ons
# -----------------------------------------------------------------------------

resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "vpc-cni"
  addon_version               = data.aws_eks_addon_version.vpc_cni.version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = merge(var.tags, { Name = "${local.cluster_name}-vpc-cni" })
  depends_on                  = [aws_eks_node_group.workers]
}

resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "coredns"
  addon_version               = data.aws_eks_addon_version.coredns.version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = merge(var.tags, { Name = "${local.cluster_name}-coredns" })
  depends_on                  = [aws_eks_node_group.workers]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "kube-proxy"
  addon_version               = data.aws_eks_addon_version.kube_proxy.version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = merge(var.tags, { Name = "${local.cluster_name}-kube-proxy" })
  depends_on                  = [aws_eks_node_group.workers]
}

resource "aws_eks_addon" "ebs_csi_driver" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "aws-ebs-csi-driver"
  addon_version               = data.aws_eks_addon_version.ebs_csi.version
  service_account_role_arn    = aws_iam_role.ebs_csi.arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = merge(var.tags, { Name = "${local.cluster_name}-ebs-csi-driver" })
  depends_on                  = [aws_eks_node_group.workers]
}

resource "aws_eks_addon" "cloudwatch_observability" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "amazon-cloudwatch-observability"
  addon_version               = data.aws_eks_addon_version.cloudwatch_observability.version
  service_account_role_arn    = aws_iam_role.cloudwatch_observability.arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = merge(var.tags, { Name = "${local.cluster_name}-cloudwatch-observability" })
  depends_on                  = [aws_eks_node_group.workers]
}
