output "rotation_lambda_arn" {
  description = "ARN of the AWS-managed Lambda function performing Secrets Manager rotation."
  value       = local.rotation_lambda_arn
}

output "rotation_lambda_security_group_id" {
  description = "ID of the security group attached to the rotation Lambda."
  value       = aws_security_group.rotation_lambda.id
}

output "rotation_schedule_days" {
  description = "Configured rotation interval in days."
  value       = var.rotation_days
}
