# ---------------------------------------------------------------------------
# Repository URLs -- used as image references in ECS task definitions
# ---------------------------------------------------------------------------

output "api_repository_url" {
  description = "ECR repository URL for the FastAPI backend image"
  value       = aws_ecr_repository.this["api"].repository_url
}

output "worker_repository_url" {
  description = "ECR repository URL for the Celery worker image"
  value       = aws_ecr_repository.this["worker"].repository_url
}

output "frontend_repository_url" {
  description = "ECR repository URL for the Next.js frontend image"
  value       = aws_ecr_repository.this["frontend"].repository_url
}

output "terraform_runner_repository_url" {
  description = "ECR repository URL for the ephemeral Terraform runner image"
  value       = aws_ecr_repository.this["terraform_runner"].repository_url
}

# ---------------------------------------------------------------------------
# Repository ARNs -- used for IAM policies granting push/pull access
# ---------------------------------------------------------------------------

output "api_repository_arn" {
  description = "ECR repository ARN for the FastAPI backend image"
  value       = aws_ecr_repository.this["api"].arn
}

output "worker_repository_arn" {
  description = "ECR repository ARN for the Celery worker image"
  value       = aws_ecr_repository.this["worker"].arn
}
