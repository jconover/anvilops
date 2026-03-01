variable "project_name" {
  description = "Project name used as prefix for ECS resources"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for CloudWatch logs and container environment"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs where Fargate tasks will run"
  type        = list(string)
}

variable "ecs_runner_security_group_id" {
  description = "Security group ID attached to the Terraform runner Fargate tasks"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "IAM role ARN for ECS task execution (image pull, log push, secret fetch)"
  type        = string
}

variable "ecs_terraform_runner_role_arn" {
  description = "IAM task role ARN granting Terraform the permissions it needs to provision infrastructure"
  type        = string
}

variable "terraform_runner_image" {
  description = "Full ECR image URL for the Terraform runner container (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/anvilops-terraform-runner:v1.0.0)"
  type        = string
}

variable "state_bucket_name" {
  description = "S3 bucket name used for Terraform remote state storage"
  type        = string
}

variable "use_lockfile" {
  description = "Enable S3-native state locking (use_lockfile). Replaces deprecated DynamoDB locking."
  type        = bool
  default     = true
}

variable "db_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the DATABASE_URL connection string"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all ECS runner resources"
  type        = map(string)
  default     = {}
}
