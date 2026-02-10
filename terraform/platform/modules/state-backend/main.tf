# =============================================================================
# AnvilOps Terraform State Backend
# =============================================================================
# Bootstrap module — creates S3 bucket + DynamoDB table for remote state.
# Apply this BEFORE the main platform stack, then migrate state with:
#   terraform init -migrate-state
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id        = data.aws_caller_identity.current.account_id
  region            = data.aws_region.current.name
  state_bucket_name = "${var.project_name}-terraform-state-${var.environment}-${local.account_id}"
  plans_bucket_name = "${var.project_name}-terraform-plans-${var.environment}-${local.account_id}"
  lock_table_name   = "${var.project_name}-terraform-locks-${var.environment}"
  use_kms           = var.kms_key_arn != ""
}

# =============================================================================
# State Bucket
# =============================================================================

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket_name

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(var.tags, {
    Name    = local.state_bucket_name
    Purpose = "terraform-state"
  })
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.use_kms ? "aws:kms" : "AES256"
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = local.use_kms
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket     = aws_s3_bucket.state.id
  depends_on = [aws_s3_bucket_versioning.state]

  rule {
    id     = "state-noncurrent-version-management"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_transition {
      noncurrent_days = var.noncurrent_version_glacier_days
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {
      prefix = ""
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket     = aws_s3_bucket.state.id
  depends_on = [aws_s3_bucket_public_access_block.state]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceSSLOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.state.arn,
          "${aws_s3_bucket.state.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "DenyUnencryptedObjectUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.state.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = local.use_kms ? "aws:kms" : "AES256"
          }
        }
      },
    ]
  })
}

# =============================================================================
# DynamoDB Lock Table
# =============================================================================

resource "aws_dynamodb_table" "locks" {
  name         = local.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = local.use_kms ? var.kms_key_arn : null
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(var.tags, {
    Name    = local.lock_table_name
    Purpose = "terraform-state-locking"
  })
}

# =============================================================================
# Plans Artifact Bucket (CI/CD)
# =============================================================================

resource "aws_s3_bucket" "plans" {
  count  = var.enable_plans_bucket ? 1 : 0
  bucket = local.plans_bucket_name

  tags = merge(var.tags, {
    Name    = local.plans_bucket_name
    Purpose = "terraform-plan-artifacts"
  })
}

resource "aws_s3_bucket_versioning" "plans" {
  count  = var.enable_plans_bucket ? 1 : 0
  bucket = aws_s3_bucket.plans[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "plans" {
  count  = var.enable_plans_bucket ? 1 : 0
  bucket = aws_s3_bucket.plans[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.use_kms ? "aws:kms" : "AES256"
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = local.use_kms
  }
}

resource "aws_s3_bucket_public_access_block" "plans" {
  count  = var.enable_plans_bucket ? 1 : 0
  bucket = aws_s3_bucket.plans[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "plans" {
  count      = var.enable_plans_bucket ? 1 : 0
  bucket     = aws_s3_bucket.plans[0].id
  depends_on = [aws_s3_bucket_versioning.plans]

  rule {
    id     = "expire-old-plan-artifacts"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = var.plans_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {
      prefix = ""
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 3
    }
  }
}

resource "aws_s3_bucket_policy" "plans" {
  count      = var.enable_plans_bucket ? 1 : 0
  bucket     = aws_s3_bucket.plans[0].id
  depends_on = [aws_s3_bucket_public_access_block.plans]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceSSLOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.plans[0].arn,
          "${aws_s3_bucket.plans[0].arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
    ]
  })
}
