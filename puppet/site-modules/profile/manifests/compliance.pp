# @summary Master compliance profile aggregating CIS/STIG security checks
#
# This profile serves as the entry point for all compliance enforcement on
# AnvilOps-managed servers. It includes OS-specific compliance sub-profiles,
# coordinates with the existing profile::security hardening layer, and exposes
# compliance posture through custom Facter facts that Puppet Enterprise can
# display on node dashboards and use in PuppetDB queries.
#
# The custom fact `anvilops_compliance` reports per-check pass/fail status
# and an aggregate compliance score, enabling PE Console reporting and
# automated compliance evidence collection.
#
# @param cis_level
#   CIS benchmark level to enforce. Level 1 is the practical baseline suitable
#   for most servers. Level 2 adds defense-in-depth controls that may impact
#   usability or performance (e.g., disabling USB storage, additional audit
#   granularity). Default: 1.
#
# @param stig_enabled
#   Whether to apply DISA STIG controls in addition to CIS benchmarks.
#   STIG controls are more prescriptive and are typically required only for
#   government or defense-adjacent workloads. Default: false.
#
# @param report_only
#   When true, compliance resources are applied in noop mode. Puppet will
#   report what WOULD change without making modifications. Useful for
#   initial audits or pre-production assessment. Default: false.
#
# @param enforce_file_permissions
#   Whether to enforce CIS file permission controls on critical system files.
#   Default: true.
#
# @param enforce_network_hardening
#   Whether to enforce CIS network stack hardening (sysctl parameters,
#   IP forwarding, ICMP settings). Default: true.
#
# @param enforce_audit_rules
#   Whether to deploy comprehensive auditd rules (Linux) or advanced audit
#   policy (Windows). Default: true.
#
# @example Default CIS Level 1 enforcement
#   include profile::compliance
#
# @example CIS Level 2 with STIG
#   class { 'profile::compliance':
#     cis_level    => 2,
#     stig_enabled => true,
#   }
#
# @example Audit-only mode for initial assessment
#   class { 'profile::compliance':
#     report_only => true,
#   }
#
class profile::compliance (
  Integer[1,2] $cis_level               = 1,
  Boolean      $stig_enabled            = false,
  Boolean      $report_only             = false,
  Boolean      $enforce_file_permissions = true,
  Boolean      $enforce_network_hardening = true,
  Boolean      $enforce_audit_rules     = true,
) {
  # ------------------------------------------------------------------
  # Dependency: the existing security profile provides foundational
  # hardening (SSH, password policy, disabled filesystems, audit basics).
  # Compliance builds on top of it with more granular CIS/STIG controls.
  # ------------------------------------------------------------------
  include profile::security

  # ------------------------------------------------------------------
  # If report_only is set, schedule a noop override for all compliance
  # resources. This lets PE show what would be enforced without changing
  # the system, which is valuable for initial compliance gap analysis.
  # ------------------------------------------------------------------
  if $report_only {
    schedule { 'compliance-noop':
      period => 'always',
    }

    # Tag all compliance resources for selective noop via PE orchestrator
    tag('compliance_audit')
  }

  # ------------------------------------------------------------------
  # OS-specific compliance enforcement
  # ------------------------------------------------------------------
  case $facts['os']['family'] {
    'windows': {
      class { 'profile::compliance::windows':
        cis_level               => $cis_level,
        stig_enabled            => $stig_enabled,
        report_only             => $report_only,
        enforce_audit_rules     => $enforce_audit_rules,
      }
    }
    'RedHat', 'Debian': {
      class { 'profile::compliance::linux':
        cis_level                 => $cis_level,
        stig_enabled              => $stig_enabled,
        report_only               => $report_only,
        enforce_file_permissions  => $enforce_file_permissions,
        enforce_network_hardening => $enforce_network_hardening,
        enforce_audit_rules       => $enforce_audit_rules,
      }
    }
    default: {
      notify { 'compliance-unsupported-os':
        message => "profile::compliance: No compliance controls available for OS family ${facts['os']['family']}",
      }
    }
  }

  # ------------------------------------------------------------------
  # Compliance metadata file consumed by the anvilops_metadata fact
  # and the AnvilOps API for dashboard reporting.
  # ------------------------------------------------------------------
  $metadata_dir = $facts['os']['family'] ? {
    'windows' => 'C:/ProgramData/AnvilOps',
    default   => '/etc/anvilops',
  }

  $metadata_file = "${metadata_dir}/compliance_config.json"

  file { $metadata_dir:
    ensure => directory,
  }

  # Write compliance configuration so facts can report active settings
  file { $metadata_file:
    ensure  => file,
    content => stdlib::to_json_pretty({
      'cis_level'    => $cis_level,
      'stig_enabled' => $stig_enabled,
      'report_only'  => $report_only,
      'last_applied' => Timestamp.new(),
    }),
    require => File[$metadata_dir],
  }
}
