# =============================================================================
# AnvilOps DNS Module
# =============================================================================
# Route 53 hosted zone, DNS records (root, API, app, auth), ACM validation
# records, and API health check with CloudWatch alarm.
# =============================================================================

locals {
  # Use existing zone if provided, otherwise create a new one
  use_existing_zone = var.existing_zone_id != ""
  zone_id           = local.use_existing_zone ? var.existing_zone_id : aws_route53_zone.this[0].zone_id
}

# -----------------------------------------------------------------------------
# Route 53 Hosted Zone (skipped when using an existing zone)
# -----------------------------------------------------------------------------

resource "aws_route53_zone" "this" {
  count = local.use_existing_zone ? 0 : 1

  name    = var.domain_name
  comment = "AnvilOps ${var.environment} platform DNS"

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-zone" })
}

# -----------------------------------------------------------------------------
# A Record — Root Domain (alias to ALB)
# -----------------------------------------------------------------------------

resource "aws_route53_record" "root" {
  zone_id = local.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# -----------------------------------------------------------------------------
# A Record — API Subdomain (alias to ALB)
# -----------------------------------------------------------------------------

resource "aws_route53_record" "api" {
  zone_id = local.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# -----------------------------------------------------------------------------
# A Record — App Subdomain (alias to ALB)
# -----------------------------------------------------------------------------

resource "aws_route53_record" "app" {
  zone_id = local.zone_id
  name    = "app.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

# -----------------------------------------------------------------------------
# CNAME — Cognito Auth Subdomain
# -----------------------------------------------------------------------------

resource "aws_route53_record" "auth" {
  count = var.cognito_domain_url != "" ? 1 : 0

  zone_id = local.zone_id
  name    = "auth.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [var.cognito_domain_url]
}

# -----------------------------------------------------------------------------
# Route 53 Health Check — API Endpoint
# -----------------------------------------------------------------------------

resource "aws_route53_health_check" "api" {
  type              = "HTTPS"
  fqdn              = "api.${var.domain_name}"
  resource_path     = "/health"
  port              = 443
  failure_threshold = 3
  request_interval  = 30

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-api-health" })
}

# -----------------------------------------------------------------------------
# CloudWatch Alarm — Health Check Status
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "health_check" {
  count = var.enable_health_check_alarm ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-api-health-check"
  alarm_description   = "Alarm when API health check fails in ${var.environment}"
  namespace           = "AWS/Route53"
  metric_name         = "HealthCheckStatus"
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  evaluation_periods  = 2
  period              = 60
  statistic           = "Minimum"

  dimensions = {
    HealthCheckId = aws_route53_health_check.api.id
  }

  alarm_actions             = [var.sns_topic_arn]
  ok_actions                = [var.sns_topic_arn]
  insufficient_data_actions = []
  treat_missing_data        = "breaching"

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-api-health-alarm" })
}
