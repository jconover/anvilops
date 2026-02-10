# =============================================================================
# AnvilOps Platform Monitoring Module - Variables
# =============================================================================

variable "project_name" {
  description = "Name of the project. Used as a prefix for all resource names."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "alert_email" {
  description = "Email address to receive CloudWatch alarm notifications via SNS."
  type        = string

  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.[^@]+$", var.alert_email))
    error_message = "Must be a valid email address."
  }
}

variable "rds_instance_id" {
  description = "Identifier of the RDS instance to monitor (the DBInstanceIdentifier, not the ARN)."
  type        = string
}

variable "elasticache_replication_group_id" {
  description = "ID of the ElastiCache Redis replication group to monitor."
  type        = string
}

variable "alb_arn_suffix" {
  description = "ARN suffix of the Application Load Balancer (the portion after 'app/'). Used in CloudWatch metric dimensions."
  type        = string
}

variable "alb_target_group_arn_suffix" {
  description = "ARN suffix of the ALB target group. Used for unhealthy host count alarms. Leave empty to skip target-group-level alarms."
  type        = string
  default     = ""
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster running Terraform runner tasks."
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service for the Terraform runner. Used for task failure alarms."
  type        = string
  default     = ""
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster running the AnvilOps platform workloads."
  type        = string
}

variable "enable_metric_filters" {
  description = "Whether to create CloudWatch metric filters for error log patterns. Set to true once applications are logging to CloudWatch."
  type        = bool
  default     = true
}

variable "alarm_actions_enabled" {
  description = "Whether alarm actions (SNS notifications) are enabled. Set to false in dev to avoid noise during development."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags to apply to all resources created by this module."
  type        = map(string)
  default     = {}
}
