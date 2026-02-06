# @summary Application server role
#
# Provisions an application server with .NET (Windows) or Java (Linux).
# Includes security hardening and application runtime configuration.
#
# Includes:
# - All base server configuration
# - Security hardening
# - OS-specific application runtime (.NET or Java)
# - Application-specific firewall rules
#
# @example Assign to a Windows .NET app server
#   node 'PROD-APP-j4k9.anvilops.local' {
#     include role::app_server
#   }
#
# @example Assign to a Linux Java app server
#   node 'PROD-APP-r8v2.anvilops.local' {
#     include role::app_server
#   }
#
class role::app_server {
  # Foundation - all servers need these
  include profile::base
  include profile::monitoring
  include profile::patching
  include profile::firewall

  # Security hardening for application servers
  include profile::security

  # OS-specific application runtime configuration
  case $facts['os']['family'] {
    'windows': {
      # Windows-specific base configuration
      include profile::windows_base

      # .NET Framework and runtime components
      include profile::dotnet
    }
    default: {
      # Linux-specific base configuration
      include profile::linux_base

      # Java JDK/JRE and runtime configuration
      include profile::java
    }
  }
}
