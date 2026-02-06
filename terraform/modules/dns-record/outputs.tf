output "fqdn" {
  description = "The fully qualified domain name of the DNS record."
  value       = aws_route53_record.this.fqdn
}

output "record_name" {
  description = "The name of the DNS record."
  value       = aws_route53_record.this.name
}
