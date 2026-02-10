output "db_instance_id" {
  description = "Identifier of the RDS instance."
  value       = aws_db_instance.this.id
}

output "db_endpoint" {
  description = "DNS hostname of the RDS instance (address only, no port)."
  value       = aws_db_instance.this.address
}

output "db_port" {
  description = "Port the RDS instance is listening on."
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Name of the default database."
  value       = aws_db_instance.this.db_name
}

output "db_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials."
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "db_instance_arn" {
  description = "ARN of the RDS instance."
  value       = aws_db_instance.this.arn
}

output "db_kms_key_arn" {
  description = "ARN of the KMS key used for RDS storage encryption."
  value       = aws_kms_key.rds.arn
}
