variable "project_name" {
  description = "Project name used as a prefix for all Cognito resources."
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

variable "callback_urls" {
  description = "List of allowed callback URLs for the Cognito user pool client."
  type        = list(string)
}

variable "logout_urls" {
  description = "List of allowed logout URLs for the Cognito user pool client."
  type        = list(string)
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection on the Cognito user pool."
  type        = bool
  default     = true
}

variable "ses_email_identity_arn" {
  description = "ARN of a verified SES email identity. Leave empty to use Cognito default email."
  type        = string
  default     = ""
}

variable "ses_from_email" {
  description = "From email address when using SES. Required if ses_email_identity_arn is set."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all Cognito resources."
  type        = map(string)
  default     = {}
}
