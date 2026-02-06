# =============================================================================
# Template: App Server (Java)
# =============================================================================
# Amazon Linux 2023, Medium (4 vCPU/16GB), JDK 21 + Tomcat
# Internal only, no domain join
# =============================================================================

os_type          = "amazon_linux_2023"
instance_size    = "medium"
security_profile = "internal_only"
domain_join      = false
puppet_role      = "app_server"
root_volume_size = 30

additional_storage = []

tags = {
  Template = "app-server-java"
  Role     = "application"
}
