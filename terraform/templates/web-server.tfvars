# =============================================================================
# Template: Standard Web Server
# =============================================================================
# Windows Server 2022, Medium (4 vCPU/16GB), IIS + .NET 8
# AD-joined, internal-facing
# =============================================================================

os_type          = "windows_2022"
instance_size    = "medium"
security_profile = "web_facing"
domain_join      = true
puppet_role      = "web_server"
root_volume_size = 50

additional_storage = []

tags = {
  Template = "standard-web-server"
  Role     = "web"
}
