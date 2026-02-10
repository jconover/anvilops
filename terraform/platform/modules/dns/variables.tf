variable "project_name" {
  description = "Name of the project."
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

variable "domain_name" {
  description = "Root domain name for the hosted zone (e.g., anvilops.example.com)."
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  type        = string
}

variable "alb_zone_id" {
  description = "Route 53 hosted zone ID of the Application Load Balancer."
  type        = string
}

variable "cognito_domain_url" {
  description = "Cognito domain URL for the auth CNAME. Leave empty to skip."
  type        = string
  default     = ""
}

variable "acm_domain_validation_options" {
  description = "ACM certificate domain validation options for DNS validation records."
  type = list(object({
    domain_name           = string
    resource_record_name  = string
    resource_record_type  = string
    resource_record_value = string
  }))
  default = []
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for health check alarms. Leave empty to skip."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
