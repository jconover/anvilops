# -----------------------------------------------------------------------------
# ALB Module - Outputs
# -----------------------------------------------------------------------------

output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.this.arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = aws_lb.this.dns_name
}

output "alb_arn_suffix" {
  description = "ARN suffix of the ALB (for CloudWatch metric dimensions)."
  value       = aws_lb.this.arn_suffix
}

output "alb_zone_id" {
  description = "Canonical hosted zone ID of the ALB (for Route 53 alias records)."
  value       = aws_lb.this.zone_id
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener."
  value       = aws_lb_listener.https.arn
}

output "frontend_target_group_arn" {
  description = "ARN of the frontend (Next.js) target group."
  value       = aws_lb_target_group.frontend.arn
}

output "api_target_group_arn" {
  description = "ARN of the API (FastAPI) target group."
  value       = aws_lb_target_group.api.arn
}

output "acm_certificate_arn" {
  description = "ARN of the validated ACM certificate."
  value       = aws_acm_certificate.this.arn
}

output "acm_certificate_domain_validation_options" {
  description = "Domain validation options for the ACM certificate. Use these to create DNS validation records in your DNS module."
  value       = aws_acm_certificate.this.domain_validation_options
}

output "waf_web_acl_arn" {
  description = "ARN of the WAF v2 Web ACL. Empty string if WAF is disabled."
  value       = var.enable_waf ? aws_wafv2_web_acl.this[0].arn : ""
}

output "alb_logs_bucket_name" {
  description = "Name of the S3 bucket used for ALB access logs."
  value       = aws_s3_bucket.alb_logs.id
}
