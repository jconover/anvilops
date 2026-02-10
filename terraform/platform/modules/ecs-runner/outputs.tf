output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster running ephemeral Terraform tasks"
  value       = aws_ecs_cluster.this.arn
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster running ephemeral Terraform tasks"
  value       = aws_ecs_cluster.this.name
}

output "task_definition_arn" {
  description = "ARN of the Terraform runner ECS task definition"
  value       = aws_ecs_task_definition.terraform_runner.arn
}

output "task_definition_family" {
  description = "Family name of the Terraform runner ECS task definition"
  value       = aws_ecs_task_definition.terraform_runner.family
}

output "log_group_name" {
  description = "CloudWatch log group name for Terraform runner task logs"
  value       = aws_cloudwatch_log_group.terraform_runner.name
}
