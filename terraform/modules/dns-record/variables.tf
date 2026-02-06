variable "zone_id" {
  description = "Route53 hosted zone ID where the DNS record will be created."
  type        = string
}

variable "record_name" {
  description = "The DNS record name (e.g., 'myserver.internal.example.com')."
  type        = string
}

variable "record_type" {
  description = "The DNS record type (A, AAAA, CNAME)."
  type        = string
  default     = "A"

  validation {
    condition     = contains(["A", "AAAA", "CNAME"], var.record_type)
    error_message = "Record type must be one of: A, AAAA, CNAME."
  }
}

variable "ttl" {
  description = "Time to live for the DNS record in seconds."
  type        = number
  default     = 300
}

variable "records" {
  description = "List of record values (IP addresses for A records, hostnames for CNAME)."
  type        = list(string)
}
