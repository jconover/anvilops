variable "server_name" {
  description = "Name of the server instance. Used in the Name tag and hostname configuration."
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

variable "instance_type" {
  description = "EC2 instance type (e.g., t3.medium, m5.2xlarge). Mapped from the size selection in the API."
  type        = string
}

variable "ami_id" {
  description = "AMI ID for the Linux instance."
  type        = string
}

variable "subnet_id" {
  description = "ID of the subnet where the instance will be launched."
  type        = string
}

variable "vpc_security_group_ids" {
  description = "List of security group IDs to attach to the instance."
  type        = list(string)
}

variable "iam_instance_profile" {
  description = "Name of the IAM instance profile to attach to the instance."
  type        = string
}

variable "key_name" {
  description = "Name of the SSH key pair. Leave empty to disable SSH key-based access (SSM preferred)."
  type        = string
  default     = ""
}

variable "root_volume_size" {
  description = "Size of the root EBS volume in GB."
  type        = number
  default     = 30

  validation {
    condition     = var.root_volume_size >= 8 && var.root_volume_size <= 16384
    error_message = "Root volume size must be between 8 and 16384 GB."
  }
}

variable "root_volume_type" {
  description = "Type of the root EBS volume (gp3, gp2, io1, io2)."
  type        = string
  default     = "gp3"

  validation {
    condition     = contains(["gp3", "gp2", "io1", "io2"], var.root_volume_type)
    error_message = "Root volume type must be one of: gp3, gp2, io1, io2."
  }
}

variable "user_data" {
  description = "Custom user data script to run on instance launch. If empty, a default script is used."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to apply to the instance and its resources."
  type        = map(string)
  default     = {}
}
