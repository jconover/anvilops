variable "project_name" {
  description = "Name of the project. Used as a prefix for resource naming."
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
  description = "List of isolated/private subnet IDs for the ElastiCache subnet group."
  type        = list(string)
}

variable "redis_security_group_id" {
  description = "ID of the security group to attach to the ElastiCache replication group."
  type        = string
}

variable "redis_node_type" {
  description = "ElastiCache node instance type (e.g., cache.t3.medium, cache.r7g.large)."
  type        = string
}

variable "num_cache_clusters" {
  description = "Number of cache clusters (nodes) in the replication group. Use 2+ for automatic failover."
  type        = number
  default     = 2
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for ElastiCache event notifications. Leave empty to disable."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
