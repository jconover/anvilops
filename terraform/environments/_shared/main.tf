# =============================================================================
# AnvilOps Server Provisioning - Shared Module
# =============================================================================
# This module contains all resource logic shared across dev, staging, and
# production environments. Each environment is a thin wrapper that calls this
# module and supplies environment-specific variable defaults.
#
# Usage by the API:
#   1. terraform workspace new DEV-WEB-a3f8
#   2. terraform plan -var-file=request.tfvars
#   3. terraform apply -var-file=request.tfvars -auto-approve
#
# Decommission:
#   1. terraform workspace select DEV-WEB-a3f8
#   2. terraform destroy -var-file=request.tfvars -auto-approve
#   3. terraform workspace delete DEV-WEB-a3f8
# =============================================================================

# -----------------------------------------------------------------------------
# Local Variables
# -----------------------------------------------------------------------------

locals {
  # Instance size to EC2 instance type mapping
  # Small (2 vCPU/4GB), Medium (4/16), Large (8/32), XL (16/64)
  instance_size_map = {
    small  = "t3.medium"  # 2 vCPU / 4 GB
    medium = "t3.xlarge"  # 4 vCPU / 16 GB
    large  = "m5.2xlarge" # 8 vCPU / 32 GB
    xl     = "m5.4xlarge" # 16 vCPU / 64 GB
  }

  instance_type = local.instance_size_map[var.instance_size]

  # Determine OS family from os_type
  is_windows = startswith(var.os_type, "windows")
  is_linux   = !local.is_windows
  os_family  = local.is_windows ? "windows" : "linux"

  # Resolve AMI from the os_type key
  ami_id = var.ami_map[var.os_type]

  # Root volume size: use provided value, or fall back to OS-specific defaults
  root_volume_size = var.root_volume_size > 0 ? var.root_volume_size : (local.is_windows ? 50 : 30)

  # Resource naming
  sg_name   = "${var.server_name}-sg"
  role_name = "${var.server_name}-role"

  # Consolidated tags applied to all resources
  common_tags = merge(
    {
      ServerName   = var.server_name
      Environment  = var.environment
      OSType       = var.os_type
      OSFamily     = local.os_family
      InstanceSize = var.instance_size
      PuppetRole   = var.puppet_role
      DomainJoin   = tostring(var.domain_join)
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# IAM Role & Instance Profile
# -----------------------------------------------------------------------------

module "iam_role" {
  source = "../../modules/iam-role"

  name               = local.role_name
  environment        = var.environment
  custom_policy_arns = var.custom_policy_arns
  tags               = local.common_tags
}

# -----------------------------------------------------------------------------
# Security Group
# -----------------------------------------------------------------------------

module "security_group" {
  source = "../../modules/security-group"

  name             = local.sg_name
  vpc_id           = var.vpc_id
  security_profile = var.security_profile
  vpc_cidr         = var.vpc_cidr
  custom_rules     = var.custom_security_rules
  tags             = local.common_tags
}

# -----------------------------------------------------------------------------
# EC2 Instance - Linux
# -----------------------------------------------------------------------------

module "ec2_linux" {
  source = "../../modules/ec2-linux"
  count  = local.is_linux ? 1 : 0

  server_name            = var.server_name
  environment            = var.environment
  instance_type          = local.instance_type
  ami_id                 = local.ami_id
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [module.security_group.security_group_id]
  iam_instance_profile   = module.iam_role.instance_profile_name
  key_name               = var.key_name
  root_volume_size       = local.root_volume_size
  root_volume_type       = "gp3"
  tags                   = local.common_tags
}

# -----------------------------------------------------------------------------
# EC2 Instance - Windows
# -----------------------------------------------------------------------------

module "ec2_windows" {
  source = "../../modules/ec2-windows"
  count  = local.is_windows ? 1 : 0

  server_name            = var.server_name
  environment            = var.environment
  instance_type          = local.instance_type
  ami_id                 = local.ami_id
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [module.security_group.security_group_id]
  iam_instance_profile   = module.iam_role.instance_profile_name
  key_name               = var.key_name
  root_volume_size       = local.root_volume_size
  root_volume_type       = "gp3"
  tags                   = local.common_tags
}

# -----------------------------------------------------------------------------
# Additional EBS Volumes (optional)
# -----------------------------------------------------------------------------

module "ebs_volumes" {
  source = "../../modules/ebs-volumes"
  count  = length(var.additional_storage) > 0 ? 1 : 0

  instance_id       = local.is_linux ? module.ec2_linux[0].instance_id : module.ec2_windows[0].instance_id
  availability_zone = local.is_linux ? module.ec2_linux[0].availability_zone : module.ec2_windows[0].availability_zone
  volumes           = var.additional_storage
  tags              = local.common_tags
}

# -----------------------------------------------------------------------------
# DNS Record (optional)
# -----------------------------------------------------------------------------

module "dns_record" {
  source = "../../modules/dns-record"
  count  = var.route53_zone_id != "" ? 1 : 0

  zone_id     = var.route53_zone_id
  record_name = var.dns_suffix != "" ? "${var.server_name}.${var.dns_suffix}" : var.server_name
  record_type = "A"
  ttl         = 300
  records     = [local.is_linux ? module.ec2_linux[0].private_ip : module.ec2_windows[0].private_ip]
}
