variable "project_name" {
  description = "Project name used in resource naming and tagging."
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

variable "secret_arn" {
  description = "ARN of the Secrets Manager secret containing RDS credentials to rotate."
  type        = string
}

variable "rotation_days" {
  description = "Number of days between automatic secret rotations."
  type        = number
  default     = 30

  validation {
    condition     = var.rotation_days >= 1 && var.rotation_days <= 365
    error_message = "rotation_days must be between 1 and 365."
  }
}

variable "vpc_id" {
  description = "VPC ID in which to place the rotation Lambda's security group."
  type        = string
}

variable "vpc_subnet_ids" {
  description = "List of private subnet IDs for the rotation Lambda's VPC configuration."
  type        = list(string)
}

variable "vpc_security_group_ids" {
  description = "List of RDS security group IDs. The rotation Lambda egress rule will target these so it can reach the RDS instance."
  type        = list(string)
}

variable "rds_endpoint" {
  description = "DNS hostname of the RDS instance (address only, no port). Used for documentation and future multi-user rotation support."
  type        = string
}

variable "rotation_lambda_version" {
  description = "Semantic version of the SecretsManagerRDSPostgreSQLRotationSingleUser SAR application. Pin to a specific version in production (e.g. \"1.1.367\") for change control. Defaults to latest."
  type        = string
  default     = "1.1.367"
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
