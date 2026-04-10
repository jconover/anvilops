# =============================================================================
# AnvilOps Server Provisioning - Staging Environment
# =============================================================================
# This is a thin wrapper around the shared server provisioning module.
# All resource logic lives in ../_shared. Only environment-specific defaults
# are set in this directory's variables.tf.
#
# Staging mirrors dev configuration. Auto-approved by default.
# =============================================================================

module "server" {
  source = "../_shared"

  server_name           = var.server_name
  environment           = var.environment
  os_type               = var.os_type
  instance_size         = var.instance_size
  region                = var.region
  vpc_id                = var.vpc_id
  subnet_id             = var.subnet_id
  vpc_cidr              = var.vpc_cidr
  security_profile      = var.security_profile
  custom_security_rules = var.custom_security_rules
  domain_join           = var.domain_join
  puppet_role           = var.puppet_role
  key_name              = var.key_name
  root_volume_size      = var.root_volume_size
  additional_storage    = var.additional_storage
  route53_zone_id       = var.route53_zone_id
  dns_suffix            = var.dns_suffix
  ami_map               = var.ami_map
  tags                  = var.tags
  custom_policy_arns    = var.custom_policy_arns
}
