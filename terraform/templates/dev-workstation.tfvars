# =============================================================================
# Template: Dev Workstation
# =============================================================================
# Windows Server 2022, Small (2 vCPU/4GB), VS Code + Git + Docker
# Auto-decom after 30 days, no domain join
# =============================================================================

os_type          = "windows_2022"
instance_size    = "small"
security_profile = "internal_only"
domain_join      = false
puppet_role      = "dev_workstation"
root_volume_size = 100

additional_storage = []

tags = {
  Template  = "dev-workstation"
  Role      = "development"
  AutoDecom = "30d"
}
