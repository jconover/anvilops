variable "project_name" {
  description = "Project name used as prefix for all ECR repository names"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all ECR repositories"
  type        = map(string)
  default     = {}
}
