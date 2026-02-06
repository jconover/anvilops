# @summary Developer workstation role
#
# Provisions a developer workstation (Windows) with development tools.
# Includes relaxed security policies suitable for non-production use.
#
# Features:
# - All base server configuration
# - Windows-specific configuration
# - Developer tools (VS Code, Git, Docker Desktop)
# - Relaxed security for development workflows
# - Auto-decommission tag after 30 days (enforced by AnvilOps)
#
# Security Notes:
# - Does NOT include profile::security (too restrictive for dev work)
# - Firewall rules are less restrictive
# - No compliance baselines enforced
#
# @example Assign to a developer workstation
#   node 'DEV-WKST-p2q8.anvilops.local' {
#     include role::dev_workstation
#   }
#
class role::dev_workstation {
  # Foundation - all servers need these
  include profile::base
  include profile::monitoring
  include profile::patching
  include profile::firewall

  # Windows-specific base configuration
  # Dev workstations are Windows-only in this implementation
  include profile::windows_base

  # Developer tools and productivity software
  include profile::dev_tools
}
