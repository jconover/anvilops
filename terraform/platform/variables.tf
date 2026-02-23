# =============================================================================
# AnvilOps Platform Infrastructure - Input Variables
# =============================================================================

# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Name of the project, used for resource naming and tagging."
  type        = string
  default     = "anvilops"
}

variable "environment" {
  description = "Deployment environment. Controls resource sizing, deletion protection, and approval workflows."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "aws_region" {
  description = "Primary AWS region for all platform resources."
  type        = string
  default     = "us-east-1"
}

variable "secondary_region" {
  description = "Secondary AWS region for multi-region resources (DR, state replication)."
  type        = string
  default     = "us-west-2"
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# DNS
# -----------------------------------------------------------------------------

variable "domain_name" {
  description = "Root domain name for the AnvilOps platform (e.g., anvilops.devopsnexus.io)."
  type        = string
}

variable "existing_route53_zone_id" {
  description = "ID of an existing Route 53 hosted zone. When set, DNS records are added to this zone instead of creating a new one."
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the platform VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones for high-availability deployment."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "single_nat_gateway" {
  description = "Use a single NAT Gateway instead of one per AZ. Saves ~$67/mo but reduces AZ redundancy."
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# EKS Cluster
# -----------------------------------------------------------------------------

variable "eks_cluster_version" {
  description = "Kubernetes version for the EKS cluster. AWS requires sequential minor version upgrades."
  type        = string
  default     = "1.35"
}

variable "eks_node_instance_types" {
  description = "EC2 instance types for the EKS managed node group."
  type        = list(string)
  default     = ["t3.xlarge"]
}

variable "eks_node_min_size" {
  description = "Minimum number of nodes in the EKS managed node group."
  type        = number
  default     = 2
}

variable "eks_node_max_size" {
  description = "Maximum number of nodes in the EKS managed node group."
  type        = number
  default     = 6
}

variable "eks_node_desired_size" {
  description = "Desired number of nodes in the EKS managed node group."
  type        = number
  default     = 3
}

# -----------------------------------------------------------------------------
# RDS PostgreSQL
# -----------------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class for the PostgreSQL database."
  type        = string
  default     = "db.t3.large"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for the RDS instance in GB."
  type        = number
  default     = 50
}

variable "db_name" {
  description = "Name of the PostgreSQL database."
  type        = string
  default     = "anvilops"
}

# -----------------------------------------------------------------------------
# ElastiCache Redis
# -----------------------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node type for Redis."
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_clusters" {
  description = "Number of cache clusters in the Redis replication group."
  type        = number
  default     = 2
}

# -----------------------------------------------------------------------------
# Cognito
# -----------------------------------------------------------------------------

variable "cognito_callback_urls" {
  description = "List of allowed OAuth2 callback URLs for Cognito."
  type        = list(string)
}

variable "cognito_logout_urls" {
  description = "List of allowed logout redirect URLs for Cognito."
  type        = list(string)
}

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------

variable "enable_waf" {
  description = "Whether to enable AWS WAF on the ALB."
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Whether to enable deletion protection on RDS, ALB, and other critical resources."
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------

variable "alert_email" {
  description = "Email address for SNS alarm notifications."
  type        = string
}

# -----------------------------------------------------------------------------
# Puppet Enterprise
# -----------------------------------------------------------------------------

variable "puppet_instance_type" {
  description = "EC2 instance type for the Puppet Enterprise server."
  type        = string
  default     = "r5.xlarge"
}

variable "puppet_ami_id" {
  description = "AMI ID for the Puppet Enterprise server. Leave empty to auto-discover the latest Amazon Linux 2023 AMI."
  type        = string
  default     = ""
}
