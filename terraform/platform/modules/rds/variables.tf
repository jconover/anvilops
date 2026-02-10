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

variable "isolated_subnet_ids" {
  description = "List of isolated/private subnet IDs for the RDS subnet group."
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "ID of the security group to attach to the RDS instance."
  type        = string
}

variable "db_instance_class" {
  description = "RDS instance class (e.g., db.t3.large, db.r6g.xlarge)."
  type        = string
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB. Max allocated storage is set to 2x for autoscaling."
  type        = number
}

variable "db_name" {
  description = "Name of the default database to create."
  type        = string
  default     = "anvilops"
}

variable "enable_deletion_protection" {
  description = "Whether to enable deletion protection on the RDS instance."
  type        = bool
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
