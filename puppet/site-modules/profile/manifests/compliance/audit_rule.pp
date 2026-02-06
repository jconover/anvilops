# @summary Manages a single auditd rule in the AnvilOps CIS rules file
#
# This defined type adds individual audit rules to the centralized
# /etc/audit/rules.d/anvilops-cis.rules file. Rules are managed via
# file_line to enable idempotent additions without full file replacement,
# preserving any manually-added rules while ensuring all CIS-required
# rules are present.
#
# The order parameter provides logical grouping but does not affect
# actual rule ordering within the file (auditd processes rules sequentially
# as written). The immutability rule (-e 2) should always use order => 999
# to be logically grouped last.
#
# @param rule
#   The complete audit rule string, exactly as it would appear in an
#   auditd rules file. Examples:
#   - '-w /etc/shadow -p wa -k identity'
#   - '-a always,exit -F arch=b64 -S chmod -F auid>=1000 -k perm_mod'
#   - '-e 2' (make rules immutable)
#
# @param order
#   Numeric ordering hint for documentation/readability. Rules within
#   the same range are logically grouped:
#   - 10-19: Scope (sudoers)
#   - 20-29: Logins
#   - 30-39: Sessions
#   - 40-49: Time changes
#   - 50-59: Identity changes
#   - 60-69: Network/locale changes
#   - 70-79: Permission modifications
#   - 80-89: Access control
#   - 90-99: File deletion
#   - 100-109: Kernel modules
#   - 999: Immutability lock
#
# @example Add a rule to monitor shadow file changes
#   profile::compliance::audit_rule { 'monitor-shadow':
#     rule  => '-w /etc/shadow -p wa -k identity',
#     order => 50,
#   }
#
# @example Lock audit rules (must be last)
#   profile::compliance::audit_rule { 'make-immutable':
#     rule  => '-e 2',
#     order => 999,
#   }
#
define profile::compliance::audit_rule (
  String  $rule,
  Integer $order = 50,
) {
  # This defined type only applies to Linux systems with auditd
  if $facts['os']['family'] in ['RedHat', 'Debian'] {
    file_line { "audit_rule_${title}":
      ensure => present,
      path   => '/etc/audit/rules.d/anvilops-cis.rules',
      line   => $rule,
      tag    => ['cis', 'compliance', 'audit_rules'],
      notify => Exec['cis-reload-audit-rules'],
    }
  }
}
