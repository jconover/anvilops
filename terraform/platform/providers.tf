# =============================================================================
# AnvilOps Platform Infrastructure - Provider Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# AWS Provider
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Project     = var.project_name
        Environment = var.environment
        ManagedBy   = "Terraform"
        Platform    = "AnvilOps"
      },
      var.tags
    )
  }
}

# Secondary region provider for multi-region resources (DR, replication)
provider "aws" {
  alias  = "secondary"
  region = var.secondary_region

  default_tags {
    tags = merge(
      {
        Project     = var.project_name
        Environment = var.environment
        ManagedBy   = "Terraform"
        Platform    = "AnvilOps"
      },
      var.tags
    )
  }
}

# -----------------------------------------------------------------------------
# EKS Cluster Authentication
# -----------------------------------------------------------------------------

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

# -----------------------------------------------------------------------------
# Kubernetes Provider
# -----------------------------------------------------------------------------

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)
  token                  = data.aws_eks_cluster_auth.this.token
}

# -----------------------------------------------------------------------------
# Helm Provider
# -----------------------------------------------------------------------------

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}
