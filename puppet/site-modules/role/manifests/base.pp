# @summary Base server role
#
# This is the minimum viable configuration for any AnvilOps-managed server.
# All other roles build upon this foundation.
#
# Includes:
# - Core system configuration (NTP, DNS, logging)
# - Monitoring agents (CloudWatch, custom metrics)
# - Patch management baselines
# - Host-based firewall rules
#
# @example Assign to a node
#   node 'DEV-BASE-a3f8.anvilops.local' {
#     include role::base
#   }
#
class role::base {
  # Core system configuration - required for all servers
  include profile::base

  # Monitoring and observability
  include profile::monitoring

  # OS patch management and compliance
  include profile::patching

  # Host-based firewall configuration
  include profile::firewall

  # CIS/STIG compliance enforcement and reporting
  include profile::compliance
}
