# =============================================================================
# Template: App Server (.NET)
# =============================================================================
# Windows Server 2022, Medium (4 vCPU/16GB), .NET 8 + IIS
# AD-joined, internal only
# =============================================================================

os_type          = "windows_2022"
instance_size    = "medium"
security_profile = "internal_only"
domain_join      = true
puppet_role      = "app_server"
root_volume_size = 50

additional_storage = []

tags = {
  Template = "app-server-dotnet"
  Role     = "application"
}
