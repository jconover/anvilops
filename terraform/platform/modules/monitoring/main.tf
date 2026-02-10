# =============================================================================
# AnvilOps Platform Monitoring Module
# =============================================================================
# Sets up CloudWatch alarms, dashboards, SNS topics, and log groups for the
# AnvilOps platform.
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  region      = data.aws_region.current.name
  account_id  = data.aws_caller_identity.current.account_id

  log_retention_days = {
    dev        = 30
    staging    = 90
    production = 365
  }

  retention_days = local.log_retention_days[var.environment]

  common_tags = merge(
    {
      Module      = "monitoring"
      Environment = var.environment
      ManagedBy   = "AnvilOps"
    },
    var.tags
  )

  rds_dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  elasticache_dimensions = {
    ReplicationGroupId = var.elasticache_replication_group_id
  }

  alb_dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
}

# =============================================================================
# SNS Topic for Alert Notifications
# =============================================================================

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts-${var.environment}"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.name_prefix}-alerts-policy"
    Statement = [
      {
        Sid       = "AllowCloudWatchPublish"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:*"
          }
        }
      },
      {
        Sid       = "AllowRDSPublish"
        Effect    = "Allow"
        Principal = { Service = "rds.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
      },
      {
        Sid       = "AllowElastiCachePublish"
        Effect    = "Allow"
        Principal = { Service = "elasticache.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
      },
    ]
  })
}

# =============================================================================
# CloudWatch Log Groups
# =============================================================================

resource "aws_cloudwatch_log_group" "api" {
  name              = "/anvilops/${var.environment}/api"
  retention_in_days = local.retention_days
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/anvilops/${var.environment}/worker"
  retention_in_days = local.retention_days
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/anvilops/${var.environment}/frontend"
  retention_in_days = local.retention_days
  tags              = local.common_tags
}

# Note: The terraform_runner log group is created by the ecs-runner module.
# This module references it by name in the dashboard query below.

# =============================================================================
# Metric Filters - Application Error Tracking
# =============================================================================

resource "aws_cloudwatch_log_metric_filter" "api_errors" {
  count = var.enable_metric_filters ? 1 : 0

  name           = "${local.name_prefix}-api-errors"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "?ERROR ?\"level\":\"error\" ?\"level\": \"ERROR\" ?\"levelname\": \"ERROR\""

  metric_transformation {
    name          = "APIErrors"
    namespace     = "AnvilOps/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "worker_errors" {
  count = var.enable_metric_filters ? 1 : 0

  name           = "${local.name_prefix}-worker-errors"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "?ERROR ?\"level\":\"error\" ?\"level\": \"ERROR\" ?\"levelname\": \"ERROR\" ?\"Task failed\""

  metric_transformation {
    name          = "WorkerErrors"
    namespace     = "AnvilOps/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

# =============================================================================
# RDS Alarms
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name_prefix}-rds-cpu-high"
  alarm_description   = "RDS CPU utilization exceeded 80% for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.rds_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_freeable_memory" {
  alarm_name          = "${local.name_prefix}-rds-memory-low"
  alarm_description   = "RDS freeable memory dropped below 512 MB for 5 minutes."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 5
  metric_name         = "FreeableMemory"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 536870912
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.rds_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${local.name_prefix}-rds-storage-low"
  alarm_description   = "RDS free storage space dropped below 5 GB for 5 minutes."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 5
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 5368709120
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.rds_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.name_prefix}-rds-connections-high"
  alarm_description   = "RDS database connections exceeded 150 for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 150
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.rds_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_read_latency" {
  alarm_name          = "${local.name_prefix}-rds-read-latency-high"
  alarm_description   = "RDS read latency exceeded 20 ms for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "ReadLatency"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 0.020
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.rds_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

# =============================================================================
# ElastiCache (Redis) Alarms
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${local.name_prefix}-redis-cpu-high"
  alarm_description   = "Redis host CPU utilization exceeded 70% for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 70
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.elasticache_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "redis_engine_cpu" {
  alarm_name          = "${local.name_prefix}-redis-engine-cpu-high"
  alarm_description   = "Redis engine CPU utilization exceeded 80% for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "EngineCPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.elasticache_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${local.name_prefix}-redis-memory-high"
  alarm_description   = "Redis memory usage exceeded 80% for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.elasticache_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "redis_connections" {
  alarm_name          = "${local.name_prefix}-redis-connections-high"
  alarm_description   = "Redis current connections exceeded 500 for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 500
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.elasticache_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

# =============================================================================
# ALB / Application Alarms
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name_prefix}-alb-5xx-high"
  alarm_description   = "ALB 5XX errors exceeded 10 per minute for 3 consecutive minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  datapoints_to_alarm = 3
  treat_missing_data  = "notBreaching"
  dimensions          = local.alb_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_4xx" {
  alarm_name          = "${local.name_prefix}-alb-4xx-high"
  alarm_description   = "ALB target 4XX errors exceeded 100 per minute for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "HTTPCode_Target_4XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 100
  datapoints_to_alarm = 5
  treat_missing_data  = "notBreaching"
  dimensions          = local.alb_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_response_time" {
  alarm_name          = "${local.name_prefix}-alb-response-time-high"
  alarm_description   = "ALB target response time p99 exceeded 2 seconds for 5 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p99"
  threshold           = 2.0
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  dimensions          = local.alb_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  count = var.alb_target_group_arn_suffix != "" ? 1 : 0

  alarm_name          = "${local.name_prefix}-alb-unhealthy-hosts"
  alarm_description   = "ALB has unhealthy targets for 2 consecutive minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.alb_target_group_arn_suffix
  }
  actions_enabled = var.alarm_actions_enabled
  alarm_actions   = [aws_sns_topic.alerts.arn]
  ok_actions      = [aws_sns_topic.alerts.arn]
  tags            = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_no_requests" {
  alarm_name          = "${local.name_prefix}-alb-no-requests"
  alarm_description   = "ALB received zero requests for 10 minutes."
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 10
  metric_name         = "RequestCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  datapoints_to_alarm = 10
  treat_missing_data  = "breaching"
  dimensions          = local.alb_dimensions
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}

# =============================================================================
# ECS Terraform Runner Alarms
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "ecs_task_failures" {
  alarm_name          = "${local.name_prefix}-ecs-task-failures"
  alarm_description   = "More than 3 ECS Terraform runner task failures in 15 minutes."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 3
  datapoints_to_alarm = 1
  treat_missing_data  = "notBreaching"
  actions_enabled     = var.alarm_actions_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags

  metric_query {
    id          = "task_failures"
    expression  = "stopped - running"
    label       = "Task Failures"
    return_data = true
  }

  metric_query {
    id = "stopped"
    metric {
      metric_name = "ServiceCount"
      namespace   = "ECS/ContainerInsights"
      period      = 900
      stat        = "Sum"
      dimensions = {
        ClusterName = var.ecs_cluster_name
      }
    }
    label = "Stopped Tasks"
  }

  metric_query {
    id = "running"
    metric {
      metric_name = "RunningTaskCount"
      namespace   = "ECS/ContainerInsights"
      period      = 900
      stat        = "Average"
      dimensions = {
        ClusterName = var.ecs_cluster_name
      }
    }
    label = "Running Tasks"
  }
}

# =============================================================================
# CloudWatch Dashboard
# =============================================================================

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      # Row 1: ALB Traffic & Latency
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "ALB Request Count"
          region = local.region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix, { label = "Requests/min" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "ALB Response Time (p50 / p95 / p99)"
          region = local.region
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p50", label = "p50" }],
            ["...", { stat = "p95", label = "p95" }],
            ["...", { stat = "p99", label = "p99" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Seconds" } }
          annotations = { horizontal = [{ value = 2.0, label = "p99 Alarm (2s)", color = "#d62728" }] }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "ALB HTTP Error Rate"
          region = local.region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", var.alb_arn_suffix, { label = "ELB 5XX", color = "#d62728" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix, { label = "Target 5XX", color = "#ff7f0e" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", var.alb_arn_suffix, { label = "Target 4XX", color = "#ffbb78" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
        }
      },
      # Row 2: RDS PostgreSQL
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 6
        height = 6
        properties = {
          title  = "RDS CPU Utilization"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id, { label = "CPU %" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, max = 100, label = "Percent" } }
          annotations = { horizontal = [{ value = 80, label = "Alarm Threshold", color = "#d62728" }] }
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 6
        width  = 6
        height = 6
        properties = {
          title  = "RDS Freeable Memory"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/RDS", "FreeableMemory", "DBInstanceIdentifier", var.rds_instance_id, { label = "Freeable Memory" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Bytes" } }
          annotations = { horizontal = [{ value = 536870912, label = "512 MB Threshold", color = "#d62728" }] }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 6
        height = 6
        properties = {
          title  = "RDS Database Connections"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.rds_instance_id, { label = "Connections" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
          annotations = { horizontal = [{ value = 150, label = "Alarm Threshold", color = "#d62728" }] }
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 6
        width  = 6
        height = 6
        properties = {
          title  = "RDS Read / Write Latency"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/RDS", "ReadLatency", "DBInstanceIdentifier", var.rds_instance_id, { label = "Read Latency" }],
            ["AWS/RDS", "WriteLatency", "DBInstanceIdentifier", var.rds_instance_id, { label = "Write Latency" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Seconds" } }
          annotations = { horizontal = [{ value = 0.020, label = "20 ms Threshold", color = "#d62728" }] }
        }
      },
      # Row 3: ElastiCache Redis
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 6
        height = 6
        properties = {
          title  = "Redis CPU Utilization"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "ReplicationGroupId", var.elasticache_replication_group_id, { label = "Host CPU %" }],
            ["AWS/ElastiCache", "EngineCPUUtilization", "ReplicationGroupId", var.elasticache_replication_group_id, { label = "Engine CPU %" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, max = 100, label = "Percent" } }
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 12
        width  = 6
        height = 6
        properties = {
          title  = "Redis Memory Usage"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "ReplicationGroupId", var.elasticache_replication_group_id, { label = "Memory %" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, max = 100, label = "Percent" } }
          annotations = { horizontal = [{ value = 80, label = "Alarm Threshold", color = "#d62728" }] }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 6
        height = 6
        properties = {
          title  = "Redis Cache Hit Rate"
          region = local.region
          period = 60
          metrics = [
            ["AWS/ElastiCache", "CacheHits", "ReplicationGroupId", var.elasticache_replication_group_id, { stat = "Sum", label = "Hits" }],
            ["AWS/ElastiCache", "CacheMisses", "ReplicationGroupId", var.elasticache_replication_group_id, { stat = "Sum", label = "Misses" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 12
        width  = 6
        height = 6
        properties = {
          title  = "Redis Current Connections"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ElastiCache", "CurrConnections", "ReplicationGroupId", var.elasticache_replication_group_id, { label = "Connections" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
          annotations = { horizontal = [{ value = 500, label = "Alarm Threshold", color = "#d62728" }] }
        }
      },
      # Row 4: EKS Cluster
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 8
        height = 6
        properties = {
          title  = "EKS Node CPU Utilization"
          region = local.region
          stat   = "Average"
          period = 300
          metrics = [
            ["ContainerInsights", "node_cpu_utilization", "ClusterName", var.eks_cluster_name, { label = "Node CPU %" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, max = 100, label = "Percent" } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 18
        width  = 8
        height = 6
        properties = {
          title  = "EKS Node Memory Utilization"
          region = local.region
          stat   = "Average"
          period = 300
          metrics = [
            ["ContainerInsights", "node_memory_utilization", "ClusterName", var.eks_cluster_name, { label = "Node Memory %" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, max = 100, label = "Percent" } }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 18
        width  = 8
        height = 6
        properties = {
          title  = "EKS Running Pods"
          region = local.region
          stat   = "Average"
          period = 300
          metrics = [
            ["ContainerInsights", "number_of_running_pods", "ClusterName", var.eks_cluster_name, { label = "Running Pods" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
        }
      },
      # Row 5: ECS Terraform Runner
      {
        type   = "metric"
        x      = 0
        y      = 24
        width  = 8
        height = 6
        properties = {
          title  = "ECS TF Runner Task Count"
          region = local.region
          stat   = "Average"
          period = 300
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, { label = "Running Tasks" }],
            ["ECS/ContainerInsights", "PendingTaskCount", "ClusterName", var.ecs_cluster_name, { label = "Pending Tasks" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 24
        width  = 8
        height = 6
        properties = {
          title  = "ECS TF Runner CPU / Memory"
          region = local.region
          stat   = "Average"
          period = 300
          metrics = [
            ["ECS/ContainerInsights", "CpuUtilized", "ClusterName", var.ecs_cluster_name, { label = "CPU Utilized" }],
            ["ECS/ContainerInsights", "MemoryUtilized", "ClusterName", var.ecs_cluster_name, { label = "Memory Utilized" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Units" } }
        }
      },
      {
        type   = "log"
        x      = 16
        y      = 24
        width  = 8
        height = 6
        properties = {
          title  = "TF Runner Recent Errors"
          region = local.region
          query  = "SOURCE '/ecs/${var.project_name}-terraform-runner-${var.environment}' | fields @timestamp, @message | filter @message like /(?i)error|fail|exception/ | sort @timestamp desc | limit 20"
          view   = "table"
        }
      },
      # Row 6: Application Metrics
      {
        type   = "metric"
        x      = 0
        y      = 30
        width  = 8
        height = 6
        properties = {
          title  = "Celery Queue Depth"
          region = local.region
          stat   = "Average"
          period = 60
          metrics = [
            ["AnvilOps/${var.environment}", "CeleryQueueDepth", { label = "Queue Depth" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Tasks" } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 30
        width  = 8
        height = 6
        properties = {
          title  = "Celery Task Duration"
          region = local.region
          period = 60
          metrics = [
            ["AnvilOps/${var.environment}", "CeleryTaskDuration", { stat = "Average", label = "Avg Duration" }],
            ["AnvilOps/${var.environment}", "CeleryTaskDuration", { stat = "p95", label = "p95 Duration" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Seconds" } }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 30
        width  = 8
        height = 6
        properties = {
          title  = "Application Errors (API + Worker)"
          region = local.region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AnvilOps/${var.environment}", "APIErrors", { label = "API Errors", color = "#d62728" }],
            ["AnvilOps/${var.environment}", "WorkerErrors", { label = "Worker Errors", color = "#ff7f0e" }],
          ]
          view = "timeSeries"
          yAxis = { left = { min = 0, label = "Count" } }
        }
      },
    ]
  })
}
