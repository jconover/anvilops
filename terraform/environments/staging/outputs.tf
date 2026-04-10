# =============================================================================
# Outputs - Consumed by the AnvilOps API after terraform apply
# =============================================================================
# The API reads these outputs via `terraform output -json` and stores them
# in the database for display in the UI and for passing to AWX/Puppet.
#
# These outputs forward directly from the shared server module.
# =============================================================================

output "instance_id" {
  description = "EC2 instance ID of the provisioned server."
  value       = module.server.instance_id
}

output "private_ip" {
  description = "Private IP address of the server."
  value       = module.server.private_ip
}

output "public_ip" {
  description = "Public IP address of the server (null if not assigned)."
  value       = module.server.public_ip
}

output "private_dns" {
  description = "Private DNS name of the server."
  value       = module.server.private_dns
}

output "dns_name" {
  description = "Custom DNS FQDN if a Route53 record was created."
  value       = module.server.dns_name
}

output "security_group_id" {
  description = "ID of the security group attached to the server."
  value       = module.server.security_group_id
}

output "iam_role_arn" {
  description = "ARN of the IAM role attached to the server."
  value       = module.server.iam_role_arn
}

output "instance_profile_name" {
  description = "Name of the IAM instance profile."
  value       = module.server.instance_profile_name
}

output "availability_zone" {
  description = "Availability zone where the server is running."
  value       = module.server.availability_zone
}

output "os_family" {
  description = "OS family of the server (linux or windows)."
  value       = module.server.os_family
}

output "additional_volume_ids" {
  description = "Map of device name to EBS volume ID for additional storage."
  value       = module.server.additional_volume_ids
}
