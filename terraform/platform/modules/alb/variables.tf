# -----------------------------------------------------------------------------
# ALB Module - Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Name of the project, used as a prefix for all resource names."
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g., dev, staging, production)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "domain_name" {
  description = "Primary domain name for the ACM certificate (e.g., anvilops.example.com)."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where target groups will be created."
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the ALB. Must span at least two availability zones."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "At least two public subnets in different availability zones are required for the ALB."
  }
}

variable "alb_security_group_id" {
  description = "Security group ID to attach to the ALB."
  type        = string
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID for ACM DNS validation records."
  type        = string
}

variable "enable_waf" {
  description = "Whether to create and associate a WAF v2 Web ACL with the ALB."
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Whether to enable deletion protection on the ALB. Recommended for production."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to apply to all resources created by this module."
  type        = map(string)
  default     = {}
}
