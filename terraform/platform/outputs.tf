# =============================================================================
# AnvilOps Platform Infrastructure - Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the platform VPC."
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs."
  value       = module.networking.private_subnet_ids
}

output "public_subnet_ids" {
  description = "List of public subnet IDs."
  value       = module.networking.public_subnet_ids
}

# -----------------------------------------------------------------------------
# EKS
# -----------------------------------------------------------------------------

output "eks_cluster_name" {
  description = "Name of the EKS cluster."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "API server endpoint of the EKS cluster."
  value       = module.eks.cluster_endpoint
}

output "eks_oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA."
  value       = module.eks.oidc_provider_arn
}

output "eks_cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the EKS cluster."
  value       = module.eks.cluster_ca_certificate
  sensitive   = true
}

# -----------------------------------------------------------------------------
# IAM Roles (for Helm chart IRSA configuration)
# -----------------------------------------------------------------------------

output "alb_controller_role_arn" {
  description = "IAM role ARN for the AWS Load Balancer Controller."
  value       = module.iam.alb_controller_role_arn
}

output "external_dns_role_arn" {
  description = "IAM role ARN for External DNS."
  value       = module.iam.external_dns_role_arn
}

output "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for the Cluster Autoscaler."
  value       = module.iam.cluster_autoscaler_role_arn
}

# -----------------------------------------------------------------------------
# RDS
# -----------------------------------------------------------------------------

output "rds_endpoint" {
  description = "Connection endpoint for the RDS PostgreSQL instance."
  value       = module.rds.db_endpoint
}

output "rds_secret_arn" {
  description = "ARN of the Secrets Manager secret containing RDS credentials."
  value       = module.rds.db_secret_arn
  sensitive   = true
}

# -----------------------------------------------------------------------------
# ElastiCache Redis
# -----------------------------------------------------------------------------

output "redis_endpoint" {
  description = "Primary endpoint for the ElastiCache Redis replication group."
  value       = module.elasticache.primary_endpoint_address
}

# -----------------------------------------------------------------------------
# ECR
# -----------------------------------------------------------------------------

output "ecr_api_url" {
  description = "ECR repository URL for the API image."
  value       = module.ecr.api_repository_url
}

output "ecr_worker_url" {
  description = "ECR repository URL for the Celery worker image."
  value       = module.ecr.worker_repository_url
}

output "ecr_frontend_url" {
  description = "ECR repository URL for the Next.js frontend image."
  value       = module.ecr.frontend_repository_url
}

# -----------------------------------------------------------------------------
# Cognito
# -----------------------------------------------------------------------------

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool."
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "ID of the Cognito App Client."
  value       = module.cognito.user_pool_client_id
}

output "cognito_domain" {
  description = "Cognito hosted UI domain."
  value       = module.cognito.user_pool_domain
}

# -----------------------------------------------------------------------------
# ALB
# -----------------------------------------------------------------------------

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = module.alb.alb_dns_name
}

# -----------------------------------------------------------------------------
# DNS
# -----------------------------------------------------------------------------

output "route53_nameservers" {
  description = "Route 53 nameservers. Delegate from your registrar."
  value       = module.dns.hosted_zone_name_servers
}

# -----------------------------------------------------------------------------
# Puppet Enterprise
# -----------------------------------------------------------------------------

output "puppet_private_ip" {
  description = "Private IP address of the Puppet Enterprise server."
  value       = module.puppet.puppet_private_ip
}

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------

output "monitoring_sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications."
  value       = module.monitoring.sns_topic_arn
}

# -----------------------------------------------------------------------------
# State Backend
# -----------------------------------------------------------------------------

output "state_bucket_name" {
  description = "S3 bucket for server provisioning Terraform state."
  value       = local.state_bucket_name
}

output "state_dynamodb_table" {
  description = "DynamoDB table for server provisioning Terraform state locking."
  value       = local.lock_table_name
}
