locals {
  # Predefined security profiles
  profiles = {
    web_facing = {
      ingress = [
        {
          from_port   = 80
          to_port     = 80
          protocol    = "tcp"
          cidr_blocks = ["0.0.0.0/0"]
          description = "HTTP from anywhere"
        },
        {
          from_port   = 443
          to_port     = 443
          protocol    = "tcp"
          cidr_blocks = ["0.0.0.0/0"]
          description = "HTTPS from anywhere"
        },
        {
          from_port   = 22
          to_port     = 22
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "SSH from VPC"
        },
        {
          from_port   = 3389
          to_port     = 3389
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "RDP from VPC"
        },
        {
          from_port   = 5986
          to_port     = 5986
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "WinRM HTTPS from VPC"
        },
      ]
      egress = [
        {
          from_port   = 0
          to_port     = 0
          protocol    = "-1"
          cidr_blocks = ["0.0.0.0/0"]
          description = "All outbound traffic"
        },
      ]
    }

    internal_only = {
      ingress = [
        {
          from_port   = 0
          to_port     = 0
          protocol    = "-1"
          cidr_blocks = [var.vpc_cidr]
          description = "All traffic from VPC"
        },
      ]
      egress = [
        {
          from_port   = 0
          to_port     = 0
          protocol    = "-1"
          cidr_blocks = ["0.0.0.0/0"]
          description = "All outbound traffic"
        },
      ]
    }

    database = {
      ingress = [
        {
          from_port   = 1433
          to_port     = 1433
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "SQL Server from VPC"
        },
        {
          from_port   = 3306
          to_port     = 3306
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "MySQL from VPC"
        },
        {
          from_port   = 5432
          to_port     = 5432
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "PostgreSQL from VPC"
        },
        {
          from_port   = 22
          to_port     = 22
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "SSH from VPC"
        },
        {
          from_port   = 3389
          to_port     = 3389
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "RDP from VPC"
        },
        {
          from_port   = 5986
          to_port     = 5986
          protocol    = "tcp"
          cidr_blocks = [var.vpc_cidr]
          description = "WinRM HTTPS from VPC"
        },
      ]
      egress = [
        {
          from_port   = 0
          to_port     = 0
          protocol    = "-1"
          cidr_blocks = ["0.0.0.0/0"]
          description = "All outbound traffic"
        },
      ]
    }

    custom = {
      ingress = []
      egress  = []
    }
  }

  # Select the profile or use custom rules
  selected_profile = local.profiles[var.security_profile]

  ingress_rules = var.security_profile == "custom" ? [
    for rule in var.custom_rules : rule if rule.type == "ingress"
  ] : local.selected_profile.ingress

  egress_rules = var.security_profile == "custom" ? [
    for rule in var.custom_rules : rule if rule.type == "egress"
  ] : local.selected_profile.egress

  merged_tags = merge(
    {
      Name      = var.name
      ManagedBy = "AnvilOps"
      Profile   = var.security_profile
    },
    var.tags
  )
}

resource "aws_security_group" "this" {
  name        = var.name
  description = "AnvilOps managed security group - ${var.security_profile} profile"
  vpc_id      = var.vpc_id

  tags = local.merged_tags
}

resource "aws_vpc_security_group_ingress_rule" "this" {
  for_each = { for idx, rule in local.ingress_rules : idx => rule }

  security_group_id = aws_security_group.this.id
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  ip_protocol       = each.value.protocol
  cidr_ipv4         = each.value.cidr_blocks[0]
  description       = each.value.description

  tags = local.merged_tags
}

resource "aws_vpc_security_group_egress_rule" "this" {
  for_each = { for idx, rule in local.egress_rules : idx => rule }

  security_group_id = aws_security_group.this.id
  from_port         = each.value.from_port != 0 ? each.value.from_port : null
  to_port           = each.value.to_port != 0 ? each.value.to_port : null
  ip_protocol       = each.value.protocol
  cidr_ipv4         = each.value.cidr_blocks[0]
  description       = each.value.description

  tags = local.merged_tags
}
