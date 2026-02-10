output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "List of public subnet IDs (one per AZ)."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs (one per AZ)."
  value       = aws_subnet.private[*].id
}

output "isolated_subnet_ids" {
  description = "List of isolated subnet IDs for RDS/ElastiCache (no NAT route)."
  value       = aws_subnet.isolated[*].id
}

output "nat_gateway_ips" {
  description = "List of Elastic IP addresses assigned to NAT Gateways."
  value       = aws_eip.nat[*].public_ip
}

output "alb_security_group_id" {
  description = "ID of the ALB security group."
  value       = aws_security_group.alb.id
}

output "eks_security_group_id" {
  description = "ID of the EKS nodes security group."
  value       = aws_security_group.eks.id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group."
  value       = aws_security_group.rds.id
}

output "redis_security_group_id" {
  description = "ID of the Redis/ElastiCache security group."
  value       = aws_security_group.redis.id
}

output "ecs_runner_security_group_id" {
  description = "ID of the ECS Fargate runner security group."
  value       = aws_security_group.ecs_runner.id
}

output "puppet_security_group_id" {
  description = "ID of the Puppet Enterprise security group."
  value       = aws_security_group.puppet.id
}
