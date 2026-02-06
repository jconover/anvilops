variable "name" {
  description = "Name of the IAM role and instance profile."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)."
  type        = string
}

variable "custom_policy_arns" {
  description = "List of additional IAM policy ARNs to attach to the role."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags to apply to the IAM role and instance profile."
  type        = map(string)
  default     = {}
}
