variable "project_name" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the EKS cluster and node group."
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID for the EKS cluster control plane."
  type        = string
}

variable "node_instance_types" {
  description = "List of EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["m5.xlarge"]
}

variable "node_min_size" {
  description = "Minimum number of nodes in the managed node group."
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of nodes in the managed node group."
  type        = number
  default     = 6
}

variable "node_desired_size" {
  description = "Desired number of nodes in the managed node group."
  type        = number
  default     = 3
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster."
  type        = string
  default     = "1.35"
}

variable "enable_public_endpoint" {
  description = "Whether to enable public access to the EKS API server endpoint."
  type        = bool
  default     = false
}

variable "public_access_cidrs" {
  description = "List of CIDR blocks allowed to access the EKS API server when public endpoint is enabled."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.public_access_cidrs) == 0 || alltrue([for cidr in var.public_access_cidrs : can(cidrhost(cidr, 0))])
    error_message = "All entries in public_access_cidrs must be valid CIDR blocks."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
