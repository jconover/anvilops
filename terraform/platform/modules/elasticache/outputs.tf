output "replication_group_id" {
  description = "ID of the ElastiCache Redis replication group."
  value       = aws_elasticache_replication_group.this.id
}

output "primary_endpoint_address" {
  description = "Primary endpoint address for write operations."
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "Reader endpoint address for read-only operations."
  value       = aws_elasticache_replication_group.this.reader_endpoint_address
}

output "port" {
  description = "Port number on which the Redis cluster accepts connections."
  value       = aws_elasticache_replication_group.this.port
}

output "auth_token_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the Redis AUTH token."
  value       = aws_secretsmanager_secret.redis_auth_token.arn
}

output "configuration_endpoint_address" {
  description = "Configuration endpoint address for Redis cluster mode."
  value       = aws_elasticache_replication_group.this.configuration_endpoint_address
}
