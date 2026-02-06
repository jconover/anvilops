output "instance_id" {
  description = "ID of the EC2 instance."
  value       = aws_instance.this.id
}

output "private_ip" {
  description = "Private IP address of the instance."
  value       = aws_instance.this.private_ip
}

output "public_ip" {
  description = "Public IP address of the instance (null if not assigned)."
  value       = aws_instance.this.public_ip
}

output "private_dns" {
  description = "Private DNS name of the instance."
  value       = aws_instance.this.private_dns
}

output "availability_zone" {
  description = "Availability zone where the instance is running."
  value       = aws_instance.this.availability_zone
}
