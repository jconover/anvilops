output "state_bucket_name" {
  description = "Name of the S3 bucket storing Terraform state files."
  value       = aws_s3_bucket.state.id
}

output "state_bucket_arn" {
  description = "ARN of the S3 bucket storing Terraform state files."
  value       = aws_s3_bucket.state.arn
}

output "state_bucket_region" {
  description = "Region of the S3 state bucket."
  value       = local.region
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table used for Terraform state locking."
  value       = aws_dynamodb_table.locks.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table used for Terraform state locking."
  value       = aws_dynamodb_table.locks.arn
}

output "plans_bucket_name" {
  description = "Name of the S3 bucket for Terraform plan artifacts. Empty if disabled."
  value       = var.enable_plans_bucket ? aws_s3_bucket.plans[0].id : ""
}

output "plans_bucket_arn" {
  description = "ARN of the S3 bucket for Terraform plan artifacts. Empty if disabled."
  value       = var.enable_plans_bucket ? aws_s3_bucket.plans[0].arn : ""
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for state encryption."
  value       = aws_kms_key.state.arn
}

output "kms_key_alias" {
  description = "Alias of the KMS key used for state encryption."
  value       = aws_kms_alias.state.name
}

output "backend_config" {
  description = "Map with all values needed to configure an S3 backend block."
  value = {
    bucket       = aws_s3_bucket.state.id
    region       = local.region
    use_lockfile = true
    encrypt      = true
  }
}
