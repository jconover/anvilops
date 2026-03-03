###############################################################################
# AnvilOps Platform IAM Module - Outputs
###############################################################################

# --- IRSA Roles ---

output "api_role_arn" {
  description = "ARN of the AnvilOps API IRSA role."
  value       = aws_iam_role.api.arn
}

output "worker_role_arn" {
  description = "ARN of the Celery worker IRSA role."
  value       = aws_iam_role.worker.arn
}

output "alb_controller_role_arn" {
  description = "ARN of the AWS Load Balancer Controller IRSA role."
  value       = aws_iam_role.alb_controller.arn
}

output "external_dns_role_arn" {
  description = "ARN of the External DNS IRSA role."
  value       = aws_iam_role.external_dns.arn
}

output "cluster_autoscaler_role_arn" {
  description = "ARN of the Cluster Autoscaler IRSA role."
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "ebs_csi_driver_role_arn" {
  description = "ARN of the EBS CSI Driver IRSA role."
  value       = aws_iam_role.ebs_csi_driver.arn
}

# --- Non-IRSA Roles ---

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role (used by Fargate to pull images and inject secrets)."
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_terraform_runner_role_arn" {
  description = "ARN of the ECS task role for the Terraform runner (the role Terraform runs as)."
  value       = aws_iam_role.terraform_runner.arn
}

output "puppet_instance_profile_name" {
  description = "Name of the Puppet EC2 instance profile."
  value       = aws_iam_instance_profile.puppet.name
}

output "puppet_role_arn" {
  description = "ARN of the Puppet EC2 instance role."
  value       = aws_iam_role.puppet.arn
}

output "github_actions_deploy_role_arn" {
  description = "ARN of the GitHub Actions deploy role. Empty if OIDC is not enabled."
  value       = var.enable_github_actions_oidc ? aws_iam_role.github_actions_deploy[0].arn : ""
}
