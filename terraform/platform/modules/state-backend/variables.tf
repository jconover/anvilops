variable "project_name" {
  description = "Project name used as a prefix for all resource names."
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

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}

variable "enable_plans_bucket" {
  description = "Whether to create a secondary S3 bucket for Terraform plan artifacts from CI/CD."
  type        = bool
  default     = true
}

variable "noncurrent_version_glacier_days" {
  description = "Days before transitioning non-current state file versions to Glacier."
  type        = number
  default     = 90
}

variable "noncurrent_version_expiration_days" {
  description = "Days before permanently deleting non-current state file versions."
  type        = number
  default     = 365
}

variable "plans_expiration_days" {
  description = "Days before expiring plan artifacts in the plans bucket."
  type        = number
  default     = 90
}

variable "kms_key_arn" {
  description = "ARN of an external KMS key to use for state encryption. If empty, a dedicated KMS key is created by this module."
  type        = string
  default     = ""
}
