output "hosted_zone_id" {
  description = "ID of the Route 53 hosted zone."
  value       = aws_route53_zone.this.zone_id
}

output "hosted_zone_name_servers" {
  description = "Name servers for the hosted zone. Delegate from your registrar."
  value       = aws_route53_zone.this.name_servers
}

output "root_domain_fqdn" {
  description = "FQDN of the root domain record."
  value       = aws_route53_record.root.fqdn
}

output "api_domain_fqdn" {
  description = "FQDN of the API subdomain record."
  value       = aws_route53_record.api.fqdn
}

output "app_domain_fqdn" {
  description = "FQDN of the app subdomain record."
  value       = aws_route53_record.app.fqdn
}

output "health_check_id" {
  description = "ID of the Route 53 health check for the API endpoint."
  value       = aws_route53_health_check.api.id
}
