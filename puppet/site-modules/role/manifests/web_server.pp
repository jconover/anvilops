# @summary Web server role
#
# Provisions a web server with IIS (Windows) or Nginx (Linux).
# Includes security hardening and web-specific firewall rules.
#
# Includes:
# - All base server configuration
# - Security hardening (CIS benchmarks)
# - OS-specific web server (IIS or Nginx)
# - Web traffic firewall rules (80, 443)
#
# @example Assign to a Windows web server
#   node 'PROD-WEB-x9k2.anvilops.local' {
#     include role::web_server
#   }
#
class role::web_server {
  # Foundation - all servers need these
  include profile::base
  include profile::monitoring
  include profile::patching
  include profile::firewall

  # Security hardening for internet-facing servers
  include profile::security

  # OS-specific web server configuration
  case $facts['os']['family'] {
    'windows': {
      # Windows-specific base configuration
      include profile::windows_base

      # IIS web server with hardening
      include profile::iis
    }
    default: {
      # Linux-specific base configuration
      include profile::linux_base

      # Nginx web server with hardening
      include profile::nginx
    }
  }
}
