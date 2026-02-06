# =============================================================================
# Template: Public Web Server
# =============================================================================
# Amazon Linux 2023, Medium (4 vCPU/16GB), Nginx + Node.js
# ALB-ready, hardened, no domain join
# =============================================================================

os_type          = "amazon_linux_2023"
instance_size    = "medium"
security_profile = "web_facing"
domain_join      = false
puppet_role      = "web_server"
root_volume_size = 30

additional_storage = []

tags = {
  Template = "public-web-server"
  Role     = "web"
}
