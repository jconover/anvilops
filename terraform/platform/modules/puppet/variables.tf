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

variable "puppet_ami_id" {
  description = "AMI ID for the Puppet Enterprise instance. Leave empty to auto-discover the latest Amazon Linux 2023 AMI."
  type        = string
  default     = ""
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs. The first subnet will be used."
  type        = list(string)
}

variable "puppet_security_group_id" {
  description = "Security group ID for the Puppet Enterprise instance."
  type        = string
}

variable "puppet_instance_profile_name" {
  description = "IAM instance profile name for the Puppet Enterprise instance."
  type        = string
}

variable "domain_name" {
  description = "Domain name for the Puppet server (puppet.<domain_name>)."
  type        = string
}

variable "puppet_code_repo_url" {
  description = "Git repository URL for Puppet code (Code Manager)."
  type        = string
  default     = ""
}

variable "puppet_instance_type" {
  description = "EC2 instance type for Puppet Enterprise."
  type        = string
  default     = "r5.xlarge"
}

variable "puppet_root_volume_size" {
  description = "Size of the root EBS volume in GB."
  type        = number
  default     = 100
}

variable "puppet_data_volume_size" {
  description = "Size of the /opt/puppetlabs EBS volume in GB."
  type        = number
  default     = 200
}

variable "ssh_key_name" {
  description = "SSH key pair name. Leave empty to use SSM Session Manager only."
  type        = string
  default     = ""
}

variable "private_hosted_zone_id" {
  description = "Route 53 private hosted zone ID. Leave empty to skip DNS record."
  type        = string
  default     = ""
}

variable "puppet_enterprise_version" {
  description = "Puppet Enterprise version to install."
  type        = string
  default     = "2023.8"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
