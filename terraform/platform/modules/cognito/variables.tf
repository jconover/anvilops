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
  description = "List of allowed callback URLs for the Cognito user pool client. Must use HTTPS (http://localhost allowed for dev)."
  type        = list(string)

  validation {
    condition     = alltrue([for url in var.callback_urls : can(regex("^https://", url)) || can(regex("^http://localhost", url))])
    error_message = "All callback URLs must use HTTPS. Only http://localhost is allowed for local development."
  }
}

variable "logout_urls" {
  description = "List of allowed logout URLs for the Cognito user pool client. Must use HTTPS (http://localhost allowed for dev)."
  type        = list(string)

  validation {
    condition     = alltrue([for url in var.logout_urls : can(regex("^https://", url)) || can(regex("^http://localhost", url))])
    error_message = "All logout URLs must use HTTPS. Only http://localhost is allowed for local development."
  }
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

variable "mfa_configuration" {
  description = "MFA enforcement level for the Cognito user pool. Use ON to require MFA for all users."
  type        = string
  default     = "ON"

  validation {
    condition     = var.mfa_configuration == "ON"
    error_message = "MFA configuration must be ON. OPTIONAL is not allowed for security compliance."
  }
}

variable "tags" {
  description = "Additional tags to apply to all Cognito resources."
  type        = map(string)
  default     = {}
}
