# -----------------------------------------------------------------------------
# ALB Module - Application Load Balancer, ACM, WAF, Target Groups
# AnvilOps Platform Infrastructure
# -----------------------------------------------------------------------------

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Name        = "${local.name_prefix}-alb"
      ManagedBy   = "AnvilOps"
      Environment = var.environment
      Module      = "alb"
    },
    var.tags
  )

  # ELB service account IDs per region for S3 bucket policy
  elb_account_ids = {
    us-east-1      = "127311923021"
    us-east-2      = "033677994240"
    us-west-1      = "027434742980"
    us-west-2      = "797873946194"
    af-south-1     = "098369216593"
    ap-east-1      = "754344448648"
    ap-south-1     = "718504428378"
    ap-northeast-1 = "582318560864"
    ap-northeast-2 = "600734575887"
    ap-northeast-3 = "383597477331"
    ap-southeast-1 = "114774131450"
    ap-southeast-2 = "783225319266"
    ca-central-1   = "985666609251"
    eu-central-1   = "054676820928"
    eu-west-1      = "156460612806"
    eu-west-2      = "652711504416"
    eu-west-3      = "009996457667"
    eu-south-1     = "635631232127"
    eu-north-1     = "897822967062"
    me-south-1     = "076674570225"
    sa-east-1      = "507241528517"
  }
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# ACM Certificate
# -----------------------------------------------------------------------------

resource "aws_acm_certificate" "this" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-cert"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.this.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = var.route53_zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 60
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for record in aws_route53_record.acm_validation : record.fqdn]

  timeouts {
    create = "45m"
  }
}

# -----------------------------------------------------------------------------
# S3 Bucket for ALB Access Logs
# Note: ALB access logs only support SSE-S3 (AES256), not SSE-KMS.
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "alb_logs" {
  bucket        = "${var.project_name}-alb-logs-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-alb-logs-${var.environment}"
  })
}

resource "aws_s3_bucket_versioning" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 60
      storage_class = "GLACIER"
    }

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowELBAccessLogs"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.elb_account_ids[data.aws_region.current.name]}:root"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.alb_logs.arn}/alb/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
      },
      {
        Sid    = "AllowELBLogDelivery"
        Effect = "Allow"
        Principal = {
          Service = "delivery.logs.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.alb_logs.arn}/alb/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "AllowELBLogDeliveryAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "delivery.logs.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.alb_logs.arn
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Application Load Balancer
# -----------------------------------------------------------------------------

resource "aws_lb" "this" {
  name               = local.name_prefix
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.enable_deletion_protection
  enable_http2               = true
  drop_invalid_header_fields = true
  idle_timeout               = 120

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "alb"
    enabled = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb"
  })

  depends_on = [aws_s3_bucket_policy.alb_logs]
}

# -----------------------------------------------------------------------------
# Target Groups
# -----------------------------------------------------------------------------

resource "aws_lb_target_group" "frontend" {
  name        = "${local.name_prefix}-frontend"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }

  deregistration_delay = 30

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-frontend"
    Service = "frontend"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name_prefix}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/api/v1/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = false
  }

  deregistration_delay = 30

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-api"
    Service = "api"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# Listeners
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-http-redirect"
  })
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate_validation.this.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      message_body = "{\"error\":\"not_found\",\"message\":\"The requested resource does not exist.\"}"
      status_code  = "404"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-https"
  })
}

# -----------------------------------------------------------------------------
# Listener Rules
# -----------------------------------------------------------------------------

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rule-api"
  })
}

resource "aws_lb_listener_rule" "frontend" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rule-frontend"
  })
}

# -----------------------------------------------------------------------------
# WAF v2 Web ACL
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "this" {
  count = var.enable_waf ? 1 : 0

  name        = local.name_prefix
  description = "WAF Web ACL for ${local.name_prefix} ALB - managed by AnvilOps"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-sqli-rules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimitPerIP"
    priority = 10

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-waf"
  })
}

resource "aws_wafv2_web_acl_association" "this" {
  count = var.enable_waf ? 1 : 0

  resource_arn = aws_lb.this.arn
  web_acl_arn  = aws_wafv2_web_acl.this[0].arn
}
