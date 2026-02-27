# =============================================================================
# AnvilOps Platform Networking Module
# =============================================================================
# VPC, subnets (public/private/isolated), NAT Gateways, route tables,
# VPC Flow Logs, VPC Endpoints, and all platform security groups.
#
# Subnet CIDR layout (for /16 VPC like 10.0.0.0/16):
#   Public:   10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24
#   Private:  10.0.11.0/24, 10.0.12.0/24, 10.0.13.0/24
#   Isolated: 10.0.21.0/24, 10.0.22.0/24, 10.0.23.0/24
# =============================================================================

locals {
  name_prefix       = "${var.project_name}-${var.environment}"
  nat_gateway_count = var.single_nat_gateway ? 1 : length(var.availability_zones)
}

data "aws_region" "current" {}

# =============================================================================
# VPC
# =============================================================================

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = "${local.name_prefix}-vpc" })
}

# =============================================================================
# Internet Gateway
# =============================================================================

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${local.name_prefix}-igw" })
}

# =============================================================================
# Subnets — Public (one per AZ)
# =============================================================================

resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name                     = "${local.name_prefix}-public-${var.availability_zones[count.index]}"
    Tier                     = "public"
    "kubernetes.io/role/elb" = "1"
  })
}

# =============================================================================
# Subnets — Private (one per AZ)
# =============================================================================

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 11)
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name                              = "${local.name_prefix}-private-${var.availability_zones[count.index]}"
    Tier                              = "private"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

# =============================================================================
# Subnets — Isolated (one per AZ, no NAT route — for RDS, ElastiCache)
# =============================================================================

resource "aws_subnet" "isolated" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 21)
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-isolated-${var.availability_zones[count.index]}"
    Tier = "isolated"
  })
}

# =============================================================================
# Elastic IPs + NAT Gateways
# =============================================================================

resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${local.name_prefix}-nat-eip-${count.index + 1}" })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  count         = local.nat_gateway_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(var.tags, { Name = "${local.name_prefix}-nat-${count.index + 1}" })

  depends_on = [aws_internet_gateway.this]
}

# =============================================================================
# Route Tables — Public
# =============================================================================

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${local.name_prefix}-public-rt" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# =============================================================================
# Route Tables — Private
# =============================================================================

resource "aws_route_table" "private" {
  count  = local.nat_gateway_count
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${local.name_prefix}-private-rt-${count.index + 1}" })
}

resource "aws_route" "private_nat" {
  count                  = local.nat_gateway_count
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[count.index].id
}

resource "aws_route_table_association" "private" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[var.single_nat_gateway ? 0 : count.index].id
}

# =============================================================================
# Route Tables — Isolated (local only)
# =============================================================================

resource "aws_route_table" "isolated" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${local.name_prefix}-isolated-rt" })
}

resource "aws_route_table_association" "isolated" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.isolated[count.index].id
  route_table_id = aws_route_table.isolated.id
}

# =============================================================================
# VPC Flow Logs
# =============================================================================

resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/aws/vpc/${local.name_prefix}-flow-logs"
  retention_in_days = 30
  tags              = merge(var.tags, { Name = "${local.name_prefix}-flow-logs" })
}

resource "aws_iam_role" "flow_logs" {
  name = "${local.name_prefix}-vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
    }]
  })

  tags = merge(var.tags, { Name = "${local.name_prefix}-vpc-flow-logs-role" })
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "${local.name_prefix}-vpc-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups", "logs:DescribeLogStreams"]
      Effect   = "Allow"
      Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
    }]
  })
}

resource "aws_flow_log" "this" {
  vpc_id                   = aws_vpc.this.id
  traffic_type             = "ALL"
  iam_role_arn             = aws_iam_role.flow_logs.arn
  log_destination          = aws_cloudwatch_log_group.flow_logs.arn
  log_destination_type     = "cloud-watch-logs"
  max_aggregation_interval = 60
  tags                     = merge(var.tags, { Name = "${local.name_prefix}-flow-log" })
}

# =============================================================================
# VPC Endpoints — Gateway (S3)
# =============================================================================

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = concat(
    [aws_route_table.public.id],
    aws_route_table.private[*].id,
    [aws_route_table.isolated.id]
  )

  tags = merge(var.tags, { Name = "${local.name_prefix}-vpce-s3" })
}

# =============================================================================
# VPC Endpoints — Security Group for Interface Endpoints
# =============================================================================

resource "aws_security_group" "vpce" {
  name        = "${local.name_prefix}-vpce-sg"
  description = "Security group for VPC interface endpoints"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-vpce-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "vpce_https" {
  security_group_id = aws_security_group.vpce.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
  description       = "HTTPS from VPC CIDR"
}

resource "aws_vpc_security_group_egress_rule" "vpce_all" {
  security_group_id = aws_security_group.vpce.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "All outbound"
}

# =============================================================================
# VPC Endpoints — Interface (ECR, STS, Logs)
# =============================================================================

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = merge(var.tags, { Name = "${local.name_prefix}-vpce-ecr-api" })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = merge(var.tags, { Name = "${local.name_prefix}-vpce-ecr-dkr" })
}

resource "aws_vpc_endpoint" "sts" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.sts"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = merge(var.tags, { Name = "${local.name_prefix}-vpce-sts" })
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  tags                = merge(var.tags, { Name = "${local.name_prefix}-vpce-logs" })
}

# =============================================================================
# Security Groups — ALB
# =============================================================================

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-alb-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "HTTP from anywhere"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "HTTPS from anywhere"
}

resource "aws_vpc_security_group_egress_rule" "alb_all" {
  security_group_id = aws_security_group.alb.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "All outbound"
}

# =============================================================================
# Security Groups — EKS
# =============================================================================

resource "aws_security_group" "eks" {
  name        = "${local.name_prefix}-eks-sg"
  description = "Security group for EKS cluster nodes"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-eks-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "eks_from_alb_http" {
  security_group_id            = aws_security_group.eks.id
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
  description                  = "HTTP from ALB"
}

resource "aws_vpc_security_group_ingress_rule" "eks_from_alb_https" {
  security_group_id            = aws_security_group.eks.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
  description                  = "HTTPS from ALB"
}

resource "aws_vpc_security_group_ingress_rule" "eks_from_alb_8080" {
  security_group_id            = aws_security_group.eks.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
  description                  = "Port 8080 from ALB"
}

resource "aws_vpc_security_group_ingress_rule" "eks_self" {
  security_group_id            = aws_security_group.eks.id
  ip_protocol                  = "-1"
  referenced_security_group_id = aws_security_group.eks.id
  description                  = "All traffic from self (node-to-node)"
}

# EKS node egress - VPC internal (all protocols)
resource "aws_vpc_security_group_egress_rule" "eks_to_vpc" {
  security_group_id = aws_security_group.eks.id
  ip_protocol       = "-1"
  cidr_ipv4         = var.vpc_cidr
  description       = "All traffic within VPC"
  tags              = var.tags
}

# EKS node egress - HTTPS to internet (AWS APIs, ECR, package repos)
resource "aws_vpc_security_group_egress_rule" "eks_to_internet_https" {
  security_group_id = aws_security_group.eks.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "HTTPS to internet for AWS APIs and external dependencies"
  tags              = var.tags
}

# EKS node egress - DNS
resource "aws_vpc_security_group_egress_rule" "eks_to_dns_udp" {
  security_group_id = aws_security_group.eks.id
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  cidr_ipv4         = var.vpc_cidr
  description       = "DNS resolution within VPC"
  tags              = var.tags
}

resource "aws_vpc_security_group_egress_rule" "eks_to_dns_tcp" {
  security_group_id = aws_security_group.eks.id
  from_port         = 53
  to_port           = 53
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
  description       = "DNS resolution within VPC (TCP)"
  tags              = var.tags
}

# EKS node egress - NTP
resource "aws_vpc_security_group_egress_rule" "eks_to_ntp" {
  security_group_id = aws_security_group.eks.id
  from_port         = 123
  to_port           = 123
  ip_protocol       = "udp"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "NTP time synchronization"
  tags              = var.tags
}

# =============================================================================
# Security Groups — RDS
# =============================================================================

resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-rds-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_eks" {
  security_group_id            = aws_security_group.rds.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks.id
  description                  = "PostgreSQL from EKS"
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_ecs" {
  security_group_id            = aws_security_group.rds.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.ecs_runner.id
  description                  = "PostgreSQL from ECS runner"
}

resource "aws_vpc_security_group_egress_rule" "rds_to_vpc" {
  security_group_id = aws_security_group.rds.id
  ip_protocol       = "-1"
  cidr_ipv4         = var.vpc_cidr
  description       = "All traffic within VPC only"
  tags              = var.tags
}

# =============================================================================
# Security Groups — Redis
# =============================================================================

resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-redis-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_eks" {
  security_group_id            = aws_security_group.redis.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks.id
  description                  = "Redis from EKS"
}

resource "aws_vpc_security_group_egress_rule" "redis_to_vpc" {
  security_group_id = aws_security_group.redis.id
  ip_protocol       = "-1"
  cidr_ipv4         = var.vpc_cidr
  description       = "All traffic within VPC only"
  tags              = var.tags
}

# =============================================================================
# Security Groups — ECS Runner
# =============================================================================

resource "aws_security_group" "ecs_runner" {
  name        = "${local.name_prefix}-ecs-runner-sg"
  description = "Security group for ECS Fargate Terraform runner tasks"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-ecs-runner-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "ecs_runner_from_eks_https" {
  security_group_id            = aws_security_group.ecs_runner.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks.id
  description                  = "HTTPS callbacks from EKS"
  tags                         = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "ecs_runner_from_eks_callback" {
  security_group_id            = aws_security_group.ecs_runner.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks.id
  description                  = "Terraform state callback port from EKS"
  tags                         = var.tags
}

resource "aws_vpc_security_group_egress_rule" "ecs_runner_all" {
  security_group_id = aws_security_group.ecs_runner.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "All outbound"
}

# =============================================================================
# Security Groups — Puppet Enterprise
# =============================================================================

resource "aws_security_group" "puppet" {
  name        = "${local.name_prefix}-puppet-sg"
  description = "Security group for Puppet Enterprise server"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${local.name_prefix}-puppet-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "puppet_agent" {
  security_group_id = aws_security_group.puppet.id
  from_port         = 8140
  to_port           = 8140
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
  description       = "Puppet agent traffic from VPC"
}

resource "aws_vpc_security_group_ingress_rule" "puppet_orchestrator" {
  security_group_id = aws_security_group.puppet.id
  from_port         = 8142
  to_port           = 8142
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
  description       = "Puppet orchestrator from VPC"
}

resource "aws_vpc_security_group_ingress_rule" "puppet_console" {
  security_group_id = aws_security_group.puppet.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = var.vpc_cidr
  description       = "Puppet console HTTPS from VPC"
}

resource "aws_vpc_security_group_egress_rule" "puppet_all" {
  security_group_id = aws_security_group.puppet.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "All outbound"
}
