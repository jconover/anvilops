# =============================================================================
# AnvilOps ElastiCache Redis Module
# =============================================================================
# Provisions an ElastiCache Redis replication group for the Celery task queue
# and application caching. Includes encryption at rest/in-transit, automatic
# failover, Multi-AZ, and Secrets Manager integration for the AUTH token.
# =============================================================================

locals {
  replication_group_id = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# Subnet Group
# -----------------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "this" {
  name        = "${local.replication_group_id}-subnets"
  description = "Subnet group for AnvilOps ${var.environment} Redis cluster"
  subnet_ids  = var.isolated_subnet_ids

  tags = merge(var.tags, { Name = "${local.replication_group_id}-subnets" })
}

# -----------------------------------------------------------------------------
# Parameter Group
# -----------------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "this" {
  name        = "${local.replication_group_id}-params"
  family      = "redis7"
  description = "Custom parameter group for AnvilOps ${var.environment} Redis"

  # Evict keys with TTL set using LRU — ideal for Celery task results
  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  # Enable expired key event notifications for Celery task expiry
  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  # TCP keepalive to detect dead connections
  parameter {
    name  = "tcp-keepalive"
    value = "300"
  }

  # Disable idle timeout — Celery workers maintain long-lived connections
  parameter {
    name  = "timeout"
    value = "0"
  }

  tags = merge(var.tags, { Name = "${local.replication_group_id}-params" })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# AUTH Token stored in Secrets Manager
# -----------------------------------------------------------------------------

resource "random_password" "redis_auth_token" {
  length  = 32
  special = false # ElastiCache AUTH tokens don't support all special characters

  lifecycle {
    ignore_changes = all
  }
}

resource "aws_secretsmanager_secret" "redis_auth_token" {
  name                    = "${var.project_name}/${var.environment}/redis-auth-token"
  description             = "AUTH token for AnvilOps ${var.environment} ElastiCache Redis"
  recovery_window_in_days = var.environment == "production" ? 30 : 7

  tags = merge(var.tags, { Name = "${local.replication_group_id}-redis-auth" })
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  secret_id     = aws_secretsmanager_secret.redis_auth_token.id
  secret_string = random_password.redis_auth_token.result
}

# -----------------------------------------------------------------------------
# Replication Group
# -----------------------------------------------------------------------------

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = local.replication_group_id
  description          = "AnvilOps ${var.environment} Redis cluster"

  engine         = "redis"
  engine_version = "7.1"
  port           = 6379

  node_type          = var.redis_node_type
  num_cache_clusters = var.num_cache_clusters

  parameter_group_name = aws_elasticache_parameter_group.this.name
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [var.redis_security_group_id]

  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"
  auth_token                 = random_password.redis_auth_token.result

  # High availability
  automatic_failover_enabled = var.num_cache_clusters > 1
  multi_az_enabled           = var.num_cache_clusters > 1

  # Backup and maintenance
  snapshot_retention_limit = var.environment == "production" ? 7 : 1
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "sun:03:00-sun:04:00"

  auto_minor_version_upgrade = true
  apply_immediately          = false

  notification_topic_arn = var.sns_topic_arn != "" ? var.sns_topic_arn : null

  tags = merge(var.tags, { Name = local.replication_group_id })

  lifecycle {
    ignore_changes = [auth_token]
  }
}
