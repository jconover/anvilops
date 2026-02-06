output "volume_ids" {
  description = "Map of device name to EBS volume ID."
  value       = { for k, v in aws_ebs_volume.this : k => v.id }
}

output "volume_arns" {
  description = "Map of device name to EBS volume ARN."
  value       = { for k, v in aws_ebs_volume.this : k => v.arn }
}
