# =============================================================================
# AnvilOps RDS PostgreSQL Module
# =============================================================================
# Production-grade RDS PostgreSQL with KMS encryption, Enhanced Monitoring,
# Performance Insights, automated backups, Multi-AZ (production), and
# Secrets Manager credential storage.
# =============================================================================

locals {
  identifier = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# KMS Key for RDS Storage Encryption
# -----------------------------------------------------------------------------

resource "aws_kms_key" "rds" {
  description             = "KMS key for AnvilOps RDS storage encryption (${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.identifier}-rds-key-policy"
    Statement = [
      {
        Sid    = "EnableRootAccountAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowRDSServiceAccess"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
          "kms:CreateGrant",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
    ]
  })

  tags = merge(var.tags, { Name = "${local.identifier}-rds-kms" })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.identifier}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# -----------------------------------------------------------------------------
# IAM Role for Enhanced Monitoring
# -----------------------------------------------------------------------------

resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${local.identifier}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      },
    ]
  })

  tags = merge(var.tags, { Name = "${local.identifier}-rds-monitoring" })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# -----------------------------------------------------------------------------
# DB Subnet Group
# -----------------------------------------------------------------------------

resource "aws_db_subnet_group" "this" {
  name        = "${local.identifier}-db-subnet"
  description = "Isolated subnets for AnvilOps RDS (${var.environment})"
  subnet_ids  = var.isolated_subnet_ids

  tags = merge(var.tags, { Name = "${local.identifier}-db-subnet" })
}

# -----------------------------------------------------------------------------
# DB Parameter Group — PostgreSQL 16 Tuning
# -----------------------------------------------------------------------------

resource "aws_db_parameter_group" "this" {
  name        = "${local.identifier}-postgres16"
  family      = "postgres16"
  description = "Tuned PostgreSQL 16 parameters for AnvilOps (${var.environment})"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "log_min_duration_statement"
    value        = "1000"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_connections"
    value        = "1"
    apply_method = "immediate"
  }

  parameter {
    name         = "log_disconnections"
    value        = "1"
    apply_method = "immediate"
  }

  parameter {
    name         = "max_connections"
    value        = "200"
    apply_method = "pending-reboot"
  }

  # work_mem = 64MB = 65536 kB
  parameter {
    name         = "work_mem"
    value        = "65536"
    apply_method = "immediate"
  }

  # maintenance_work_mem = 512MB = 524288 kB
  parameter {
    name         = "maintenance_work_mem"
    value        = "524288"
    apply_method = "immediate"
  }

  # effective_cache_size = 2GB = 2097152 kB
  parameter {
    name         = "effective_cache_size"
    value        = "2097152"
    apply_method = "immediate"
  }

  tags = merge(var.tags, { Name = "${local.identifier}-postgres16" })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# Master Password
# -----------------------------------------------------------------------------

resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%^&*()-_=+"
}

# -----------------------------------------------------------------------------
# Secrets Manager — Database Credentials
# -----------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${local.identifier}/rds/credentials"
  description             = "RDS PostgreSQL credentials for AnvilOps (${var.environment})"
  kms_key_id              = aws_kms_key.rds.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 7

  tags = merge(var.tags, { Name = "${local.identifier}-db-credentials" })
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    username = "anvilops_admin"
    password = random_password.master.result
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = var.db_name
    engine   = "postgres"
  })
}

# -----------------------------------------------------------------------------
# RDS PostgreSQL Instance
# -----------------------------------------------------------------------------

resource "aws_db_instance" "this" {
  identifier = local.identifier

  engine         = "postgres"
  engine_version = "16.6"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 2
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.db_name
  username = "anvilops_admin"
  password = random_password.master.result

  multi_az = var.environment == "production" ? true : false

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.rds_security_group_id]
  publicly_accessible    = false

  parameter_group_name = aws_db_parameter_group.this.name

  backup_retention_period = var.environment == "production" ? 30 : 7
  backup_window           = "03:00-04:00"

  maintenance_window         = "sun:04:00-sun:05:00"
  auto_minor_version_upgrade = true
  apply_immediately          = false

  deletion_protection       = var.enable_deletion_protection
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = "${local.identifier}-final"

  performance_insights_enabled          = true
  performance_insights_retention_period = var.environment == "production" ? 731 : 7
  performance_insights_kms_key_id       = aws_kms_key.rds.arn

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  copy_tags_to_snapshot = true

  tags = merge(var.tags, { Name = local.identifier })

  lifecycle {
    ignore_changes = [password]
  }

  depends_on = [
    aws_iam_role_policy_attachment.rds_enhanced_monitoring,
  ]
}
