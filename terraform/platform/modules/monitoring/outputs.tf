# =============================================================================
# AnvilOps Platform Monitoring Module - Outputs
# =============================================================================

output "sns_topic_arn" {
  description = "ARN of the SNS topic used for CloudWatch alarm notifications."
  value       = aws_sns_topic.alerts.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic used for CloudWatch alarm notifications."
  value       = aws_sns_topic.alerts.name
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard."
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "dashboard_arn" {
  description = "ARN of the CloudWatch dashboard."
  value       = aws_cloudwatch_dashboard.main.dashboard_arn
}

output "api_log_group_name" {
  description = "Name of the CloudWatch log group for the API service."
  value       = aws_cloudwatch_log_group.api.name
}

output "worker_log_group_name" {
  description = "Name of the CloudWatch log group for the Celery worker service."
  value       = aws_cloudwatch_log_group.worker.name
}

output "frontend_log_group_name" {
  description = "Name of the CloudWatch log group for the Next.js frontend service."
  value       = aws_cloudwatch_log_group.frontend.name
}
