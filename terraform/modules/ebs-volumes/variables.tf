variable "instance_id" {
  description = "ID of the EC2 instance to attach the volumes to."
  type        = string
}

variable "availability_zone" {
  description = "Availability zone where the EBS volumes will be created. Must match the instance AZ."
  type        = string
}

variable "volumes" {
  description = "List of additional EBS volumes to create and attach."
  type = list(object({
    device_name = string
    size_gb     = number
    volume_type = string
    tags        = map(string)
  }))
  default = []

  validation {
    condition     = alltrue([for v in var.volumes : contains(["gp3", "gp2", "io1", "io2", "st1", "sc1"], v.volume_type)])
    error_message = "Volume type must be one of: gp3, gp2, io1, io2, st1, sc1."
  }
}

variable "tags" {
  description = "Additional tags to apply to all volumes."
  type        = map(string)
  default     = {}
}
