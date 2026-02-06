variable "name" {
  description = "Name of the security group."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where the security group will be created."
  type        = string
}

variable "security_profile" {
  description = "Predefined security profile: web_facing, internal_only, database, or custom."
  type        = string

  validation {
    condition     = contains(["web_facing", "internal_only", "database", "custom"], var.security_profile)
    error_message = "Security profile must be one of: web_facing, internal_only, database, custom."
  }
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC. Used in security profile rules to restrict internal traffic."
  type        = string
}

variable "custom_rules" {
  description = "Custom ingress/egress rules when security_profile is 'custom'. Ignored for predefined profiles."
  type = list(object({
    type        = string # ingress or egress
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    description = string
  }))
  default = []
}

variable "tags" {
  description = "Additional tags to apply to the security group."
  type        = map(string)
  default     = {}
}
