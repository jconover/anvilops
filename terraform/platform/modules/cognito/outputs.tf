output "user_pool_id" {
  description = "ID of the Cognito user pool."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "ARN of the Cognito user pool."
  value       = aws_cognito_user_pool.this.arn
}

output "user_pool_endpoint" {
  description = "Endpoint URL of the Cognito user pool (for JWT validation)."
  value       = aws_cognito_user_pool.this.endpoint
}

output "user_pool_client_id" {
  description = "ID of the Cognito user pool web client."
  value       = aws_cognito_user_pool_client.web.id
}

output "user_pool_client_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Cognito client secret."
  value       = aws_secretsmanager_secret.client_secret.arn
  sensitive   = true
}

output "user_pool_domain" {
  description = "Cognito hosted domain prefix."
  value       = aws_cognito_user_pool_domain.this.domain
}

output "user_pool_domain_url" {
  description = "Full HTTPS URL of the Cognito hosted UI domain."
  value       = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
}

output "resource_server_identifier" {
  description = "Identifier of the Cognito resource server for custom API scopes."
  value       = aws_cognito_resource_server.api.identifier
}

output "rbac_group_names" {
  description = "List of RBAC group names created in the user pool."
  value       = [for group in aws_cognito_user_group.rbac : group.name]
}
