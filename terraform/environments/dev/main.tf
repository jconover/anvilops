# =============================================================================
# AnvilOps Server Provisioning - Dev Environment
# =============================================================================
# This is a thin wrapper around the shared server provisioning module.
# All resource logic lives in ../_shared. Only environment-specific defaults
# are set in this directory's variables.tf.
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
