###############################################################################
# AnvilOps Platform IAM Module - Variables
###############################################################################

variable "project_name" {
  description = "Name of the project, used as a prefix in resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)."
  type        = string
}

variable "eks_oidc_provider_arn" {
  description = "ARN of the EKS cluster OIDC identity provider (used for IRSA trust policies)."
  type        = string
}

variable "eks_oidc_provider_url" {
  description = "URL of the EKS OIDC provider WITHOUT the https:// prefix (e.g. oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE)."
  type        = string
}

variable "state_bucket_arn" {
  description = "ARN of the S3 bucket that stores Terraform remote state."
  type        = string
}

variable "db_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the RDS database credentials."
  type        = string
}

variable "redis_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the Redis connection credentials."
  type        = string
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool. May be empty if the pool has not been created yet."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID that External DNS is permitted to manage. Scopes the ChangeResourceRecordSets permission to this single zone."
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all resources created by this module."
  type        = map(string)
  default     = {}
}

variable "enable_github_actions_oidc" {
  description = "Whether to create the GitHub Actions OIDC provider and deploy role."
  type        = bool
  default     = false
}

variable "github_actions_repos" {
  description = "List of GitHub repositories allowed to assume the deploy role (format: owner/repo)."
  type        = list(string)
  default     = []
}
