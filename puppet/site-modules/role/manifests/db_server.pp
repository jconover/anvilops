# @summary Database server role
#
# Provisions a SQL Server database server (Windows only).
# Includes aggressive security hardening and database-specific monitoring.
#
# Includes:
# - All base server configuration
# - Windows-specific hardening
# - SQL Server installation and configuration
# - Database-specific firewall rules (1433, 1434)
# - Enhanced monitoring for database metrics
#
# @example Assign to a SQL Server node
#   node 'PROD-DB-m5t7.anvilops.local' {
#     include role::db_server
#   }
#
class role::db_server {
  # Foundation - all servers need these
  include profile::base
  include profile::monitoring
  include profile::patching
  include profile::firewall

  # Security hardening - critical for database servers
  include profile::security

  # Windows-specific base configuration
  # Database servers are Windows-only in this implementation
  include profile::windows_base

  # SQL Server installation, configuration, and hardening
  include profile::sql_server
}
