output "puppet_instance_id" {
  description = "EC2 instance ID of the Puppet Enterprise server."
  value       = aws_instance.puppet_enterprise.id
}

output "puppet_private_ip" {
  description = "Private IP address of the Puppet Enterprise server."
  value       = aws_instance.puppet_enterprise.private_ip
}

output "puppet_private_dns" {
  description = "Private DNS name of the Puppet Enterprise server."
  value       = aws_instance.puppet_enterprise.private_dns
}

output "puppet_console_url" {
  description = "URL of the Puppet Enterprise console."
  value       = "https://puppet.${var.domain_name}"
}

output "puppet_console_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for the PE console admin password."
  value       = aws_secretsmanager_secret.puppet_console_password.arn
}

output "puppet_data_volume_id" {
  description = "EBS volume ID of the /opt/puppetlabs data volume."
  value       = aws_ebs_volume.puppet_data.id
}

output "cloudwatch_log_groups" {
  description = "Map of CloudWatch Log Group names for Puppet Enterprise."
  value = {
    puppet_server  = aws_cloudwatch_log_group.puppet_server.name
    puppet_console = aws_cloudwatch_log_group.puppet_console.name
    puppetdb       = aws_cloudwatch_log_group.puppetdb.name
    system         = aws_cloudwatch_log_group.puppet_system.name
  }
}
