output "instance_id" {
  description = "EC2 instance ID of the provisioned server."
  value       = local.is_linux ? module.ec2_linux[0].instance_id : module.ec2_windows[0].instance_id
}

output "private_ip" {
  description = "Private IP address of the server."
  value       = local.is_linux ? module.ec2_linux[0].private_ip : module.ec2_windows[0].private_ip
}

output "public_ip" {
  description = "Public IP address of the server (null if not assigned)."
  value       = local.is_linux ? module.ec2_linux[0].public_ip : module.ec2_windows[0].public_ip
}

output "private_dns" {
  description = "Private DNS name of the server."
  value       = local.is_linux ? module.ec2_linux[0].private_dns : module.ec2_windows[0].private_dns
}

output "dns_name" {
  description = "Custom DNS FQDN if a Route53 record was created."
  value       = var.route53_zone_id != "" ? module.dns_record[0].fqdn : null
}

output "security_group_id" {
  description = "ID of the security group attached to the server."
  value       = module.security_group.security_group_id
}

output "iam_role_arn" {
  description = "ARN of the IAM role attached to the server."
  value       = module.iam_role.role_arn
}

output "instance_profile_name" {
  description = "Name of the IAM instance profile."
  value       = module.iam_role.instance_profile_name
}

output "availability_zone" {
  description = "Availability zone where the server is running."
  value       = local.is_linux ? module.ec2_linux[0].availability_zone : module.ec2_windows[0].availability_zone
}

output "os_family" {
  description = "OS family of the server (linux or windows)."
  value       = local.os_family
}

output "additional_volume_ids" {
  description = "Map of device name to EBS volume ID for additional storage."
  value       = length(var.additional_storage) > 0 ? module.ebs_volumes[0].volume_ids : {}
}
