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

variable "vpc_cidr" {
  description = "CIDR block for the VPC (e.g. 10.0.0.0/16)."
  type        = string
}

variable "availability_zones" {
  description = "List of three availability zones for subnet distribution."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "If true, deploy a single NAT Gateway (dev). If false, one per AZ (production)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
