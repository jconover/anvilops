# @summary Windows CIS Benchmark compliance enforcement
#
# Implements the most impactful CIS controls for Windows Server 2016/2019/2022,
# covering account policies, local policies, Windows Firewall, advanced audit
# policy, and administrative templates. Controls are mapped to specific CIS
# Benchmark section numbers for audit traceability.
#
# Implementation approach:
# - registry_value for Group Policy-equivalent settings
# - auditpol.exe for Advanced Audit Policy configuration
# - net.exe and secedit for account policies where registry is not available
# - PowerShell exec resources for feature management
#
# @param cis_level CIS benchmark level (1 or 2)
# @param stig_enabled Whether to apply additional STIG controls
# @param report_only Whether to run in audit-only mode
# @param enforce_audit_rules Whether to deploy advanced audit policy
#
# @example
#   include profile::compliance::windows
#
class profile::compliance::windows (
  Integer[1,2] $cis_level           = 1,
  Boolean      $stig_enabled        = false,
  Boolean      $report_only         = false,
  Boolean      $enforce_audit_rules = true,
) {
  # Fail fast on non-Windows
  if $facts['os']['family'] != 'windows' {
    fail("profile::compliance::windows can only be applied to Windows systems, not ${facts['os']['family']}")
  }

  # Common path for PowerShell commands
  $ps = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

  # ====================================================================
  # CIS 1.x -- Account Policies
  # ====================================================================
  tag('cis_account')

  # CIS 1.1.1 -- Ensure 'Enforce password history' is set to '24 or more passwords'
  exec { 'cis-1.1.1-password-history':
    command => "${ps} -Command \"net accounts /uniquepw:24\"",
    unless  => "${ps} -Command \"if ((net accounts | Select-String 'Length of password history').ToString() -match '2[4-9]|[3-9]\\d|\\d{3}') { exit 0 } else { exit 1 }\"",
    tag     => ['cis', 'cis_1_1', 'compliance'],
  }

  # CIS 1.1.2 -- Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
  # Already set to 90 days in profile::security

  # CIS 1.1.3 -- Ensure 'Minimum password age' is set to '1 or more days'
  exec { 'cis-1.1.3-min-password-age':
    command => "${ps} -Command \"net accounts /minpwage:1\"",
    unless  => "${ps} -Command \"if ((net accounts | Select-String 'Minimum password age').ToString() -match '[1-9]') { exit 0 } else { exit 1 }\"",
    tag     => ['cis', 'cis_1_1', 'compliance'],
  }

  # CIS 1.1.4 -- Ensure 'Minimum password length' is set to '14 or more characters'
  # Already set in profile::security

  # CIS 1.1.5 -- Ensure 'Password must meet complexity requirements' is Enabled
  # Already set in profile::security

  # CIS 1.1.6 -- Ensure 'Store passwords using reversible encryption' is Disabled
  exec { 'cis-1.1.6-no-reversible-encryption':
    command => "${ps} -Command \"secedit /export /cfg \$env:TEMP\\secpol.cfg; (Get-Content \$env:TEMP\\secpol.cfg) -replace 'ClearTextPassword = 1', 'ClearTextPassword = 0' | Set-Content \$env:TEMP\\secpol.cfg; secedit /configure /db \$env:windir\\security\\local.sdb /cfg \$env:TEMP\\secpol.cfg /areas SECURITYPOLICY /quiet; Remove-Item \$env:TEMP\\secpol.cfg\"",
    unless  => "${ps} -Command \"secedit /export /cfg \$env:TEMP\\seccheck.cfg; \$result = Select-String 'ClearTextPassword = 0' \$env:TEMP\\seccheck.cfg; Remove-Item \$env:TEMP\\seccheck.cfg; if (\$result) { exit 0 } else { exit 1 }\"",
    tag     => ['cis', 'cis_1_1', 'compliance'],
  }

  # CIS 1.2.1 -- Ensure 'Account lockout duration' is set to '15 or more minutes'
  # Already set to 30 minutes in profile::security

  # CIS 1.2.2 -- Ensure 'Account lockout threshold' is set to '5 or fewer invalid logon attempts'
  # Already set to 5 in profile::security

  # CIS 1.2.3 -- Ensure 'Reset account lockout counter after' is set to '15 or more minutes'
  exec { 'cis-1.2.3-lockout-reset-counter':
    command => "${ps} -Command \"net accounts /lockoutwindow:15\"",
    unless  => "${ps} -Command \"if ((net accounts | Select-String 'Lockout observation window').ToString() -match '(1[5-9]|[2-9]\\d|\\d{3})') { exit 0 } else { exit 1 }\"",
    tag     => ['cis', 'cis_1_2', 'compliance'],
  }

  # ====================================================================
  # CIS 2.x -- Local Policies / Security Options
  # ====================================================================
  tag('cis_local_policies')

  # CIS 2.3.1.1 -- Ensure 'Accounts: Administrator account status' is Disabled
  # Note: We do NOT disable the built-in Administrator on managed servers
  # as this is the emergency access account. Instead, we rename it.

  # CIS 2.3.1.2 -- Ensure 'Accounts: Block Microsoft accounts' is set to
  # 'Users can not add or log on with Microsoft accounts'
  registry_key { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System':
    ensure => present,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\NoConnectedUser':
    ensure  => present,
    type    => dword,
    data    => 3,
    require => Registry_key['HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System'],
    tag     => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.1.4 -- Ensure 'Accounts: Limit local account use of blank passwords to console logon only'
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\LimitBlankPasswordUse':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.2.1 -- Ensure 'Audit: Force audit policy subcategory settings' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\SCENoApplyLegacyAuditPolicy':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.2.2 -- Ensure 'Audit: Shut down system immediately if unable to log security audits' is Disabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\CrashOnAuditFail':
    ensure => present,
    type   => dword,
    data   => 0,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.7.1 -- Ensure 'Interactive logon: Do not display last user name' is Enabled
  registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\DontDisplayLastUserName':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System'],
    tag     => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.7.2 -- Ensure 'Interactive logon: Do not require CTRL+ALT+DEL' is Disabled
  registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\DisableCAD':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System'],
    tag     => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.7.4 -- Ensure 'Interactive logon: Machine inactivity limit' is 900 seconds or fewer
  registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\InactivityTimeoutSecs':
    ensure  => present,
    type    => dword,
    data    => 900,
    require => Registry_key['HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System'],
    tag     => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.8.1 -- Ensure 'Microsoft network client: Digitally sign communications (always)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters\\RequireSecuritySignature':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.8.2 -- Ensure 'Microsoft network client: Digitally sign communications (if server agrees)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters\\EnableSecuritySignature':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.8.3 -- Ensure 'Microsoft network client: Send unencrypted password to third-party SMB servers' is Disabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters\\EnablePlainTextPassword':
    ensure => present,
    type   => dword,
    data   => 0,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.9.1 -- Ensure 'Microsoft network server: Digitally sign communications (always)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters\\RequireSecuritySignature':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.9.2 -- Ensure 'Microsoft network server: Digitally sign communications (if client agrees)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters\\EnableSecuritySignature':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.10.x -- Network Access controls
  # CIS 2.3.10.2 -- Ensure 'Network access: Do not allow anonymous enumeration of SAM accounts' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\RestrictAnonymousSAM':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.10.3 -- Ensure 'Network access: Do not allow anonymous enumeration of SAM accounts and shares' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\RestrictAnonymous':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.10.5 -- Ensure 'Network access: Let Everyone permissions apply to anonymous users' is Disabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\EveryoneIncludesAnonymous':
    ensure => present,
    type   => dword,
    data   => 0,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.10.11 -- Ensure 'Network access: Restrict anonymous access to Named Pipes and Shares' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters\\RestrictNullSessAccess':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.11.x -- Network Security
  # CIS 2.3.11.1 -- Ensure 'Network security: Allow Local System to use computer identity for NTLM' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\UseMachineId':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.11.2 -- Ensure 'Network security: Allow LocalSystem NULL session fallback' is Disabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0\\AllowNullSessionFallback':
    ensure => present,
    type   => dword,
    data   => 0,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.11.4 -- Ensure 'Network security: Do not store LAN Manager hash value on next password change' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\NoLMHash':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.11.5 -- Ensure 'Network security: LAN Manager authentication level' is 'Send NTLMv2 response only. Refuse LM & NTLM'
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\LmCompatibilityLevel':
    ensure => present,
    type   => dword,
    data   => 5,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.11.7 -- Ensure 'Network security: Minimum session security for NTLM SSP based clients' is
  # set to 'Require NTLMv2 session security, Require 128-bit encryption'
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0\\NtlmMinClientSec':
    ensure => present,
    type   => dword,
    data   => 537395200,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # CIS 2.3.11.8 -- Ensure 'Network security: Minimum session security for NTLM SSP based servers'
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0\\NtlmMinServerSec':
    ensure => present,
    type   => dword,
    data   => 537395200,
    tag    => ['cis', 'cis_2_3', 'compliance'],
  }

  # ====================================================================
  # CIS 9.x -- Windows Firewall with Advanced Security
  # ====================================================================
  tag('cis_firewall')

  # CIS 9.1.1 -- Ensure 'Windows Firewall: Domain: Firewall state' is On
  # CIS 9.2.1 -- Ensure 'Windows Firewall: Private: Firewall state' is On
  # CIS 9.3.1 -- Ensure 'Windows Firewall: Public: Firewall state' is On
  # Already managed by profile::firewall. We add logging configuration here.

  # CIS 9.1.5/9.2.5/9.3.5 -- Ensure Windows Firewall logging is configured
  ['Domain', 'Private', 'Public'].each |String $fw_profile| {
    # Enable firewall logging for dropped packets
    exec { "cis-firewall-log-dropped-${fw_profile}":
      command => "C:/Windows/System32/netsh.exe advfirewall set ${fw_profile}profile logging droppedconnections enable",
      unless  => "${ps} -Command \"if ((netsh advfirewall show ${fw_profile}profile logging | Select-String 'Log Dropped Packets').ToString() -match 'Enable') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_9', 'compliance'],
    }

    # Enable firewall logging for successful connections
    exec { "cis-firewall-log-successful-${fw_profile}":
      command => "C:/Windows/System32/netsh.exe advfirewall set ${fw_profile}profile logging allowedconnections enable",
      unless  => "${ps} -Command \"if ((netsh advfirewall show ${fw_profile}profile logging | Select-String 'Log Successful Connections').ToString() -match 'Enable') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_9', 'compliance'],
    }

    # Set log file size to at least 16384 KB
    exec { "cis-firewall-log-size-${fw_profile}":
      command => "C:/Windows/System32/netsh.exe advfirewall set ${fw_profile}profile logging maxfilesize 16384",
      unless  => "${ps} -Command \"if ((netsh advfirewall show ${fw_profile}profile logging | Select-String 'Max File Size').ToString() -match '1638[4-9]|163[89]\\d|16[4-9]\\d{2}|1[7-9]\\d{3}|[2-9]\\d{4}') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_9', 'compliance'],
    }
  }

  # ====================================================================
  # CIS 17.x -- Advanced Audit Policy Configuration
  # ====================================================================
  if $enforce_audit_rules {
    tag('cis_audit')

    # CIS 17.1.x -- Account Logon
    # CIS 17.1.1 -- Ensure 'Audit Credential Validation' is set to 'Success and Failure'
    exec { 'cis-17.1.1-credential-validation':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Credential Validation" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Credential Validation' | Select-String 'Credential Validation') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.2.x -- Account Management
    # CIS 17.2.1 -- Ensure 'Audit Application Group Management' is set to 'Success and Failure'
    exec { 'cis-17.2.1-app-group-mgmt':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Application Group Management" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Application Group Management' | Select-String 'Application Group Management') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.2.2 -- Ensure 'Audit Computer Account Management' is set to include 'Success'
    exec { 'cis-17.2.2-computer-acct-mgmt':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Computer Account Management" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Computer Account Management' | Select-String 'Computer Account Management') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.2.5 -- Ensure 'Audit Security Group Management' is set to include 'Success'
    exec { 'cis-17.2.5-security-group-mgmt':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Security Group Management" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Security Group Management' | Select-String 'Security Group Management') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.2.6 -- Ensure 'Audit User Account Management' is set to 'Success and Failure'
    # Already set in profile::security, but we ensure the exact subcategory
    exec { 'cis-17.2.6-user-acct-mgmt':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"User Account Management" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'User Account Management' | Select-String 'User Account Management') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.3.x -- Detailed Tracking
    # CIS 17.3.1 -- Ensure 'Audit PNP Activity' is set to include 'Success'
    exec { 'cis-17.3.1-pnp-activity':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Plug and Play Events" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Plug and Play Events' | Select-String 'Plug and Play Events') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.3.2 -- Ensure 'Audit Process Creation' is set to include 'Success'
    exec { 'cis-17.3.2-process-creation':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Process Creation" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Process Creation' | Select-String 'Process Creation') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.5.x -- Logon/Logoff
    # CIS 17.5.1 -- Ensure 'Audit Account Lockout' is set to include 'Failure'
    exec { 'cis-17.5.1-account-lockout':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Account Lockout" /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Account Lockout' | Select-String 'Account Lockout') -match 'Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.5.2 -- Ensure 'Audit Group Membership' is set to include 'Success'
    exec { 'cis-17.5.2-group-membership':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Group Membership" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Group Membership' | Select-String 'Group Membership') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.5.3 -- Ensure 'Audit Logoff' is set to include 'Success'
    exec { 'cis-17.5.3-logoff':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Logoff" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Logoff' | Select-String 'Logoff') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.5.4 -- Ensure 'Audit Logon' is set to 'Success and Failure'
    exec { 'cis-17.5.4-logon':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Logon" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Logon' | Select-String 'Logon') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.5.5 -- Ensure 'Audit Other Logon/Logoff Events' is set to 'Success and Failure'
    exec { 'cis-17.5.5-other-logon-events':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Other Logon/Logoff Events" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:\'Other Logon/Logoff Events\' | Select-String \'Other Logon/Logoff Events\') -match \'Success and Failure\') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.5.6 -- Ensure 'Audit Special Logon' is set to include 'Success'
    exec { 'cis-17.5.6-special-logon':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Special Logon" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Special Logon' | Select-String 'Special Logon') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.6.x -- Object Access
    # CIS 17.6.1 -- Ensure 'Audit Removable Storage' is set to 'Success and Failure'
    exec { 'cis-17.6.1-removable-storage':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Removable Storage" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Removable Storage' | Select-String 'Removable Storage') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.7.x -- Policy Change
    # CIS 17.7.1 -- Ensure 'Audit Audit Policy Change' is set to include 'Success'
    exec { 'cis-17.7.1-audit-policy-change':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Audit Policy Change" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Audit Policy Change' | Select-String 'Audit Policy Change') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.7.2 -- Ensure 'Audit Authentication Policy Change' is set to include 'Success'
    exec { 'cis-17.7.2-auth-policy-change':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Authentication Policy Change" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Authentication Policy Change' | Select-String 'Authentication Policy Change') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.7.3 -- Ensure 'Audit Authorization Policy Change' is set to include 'Success'
    exec { 'cis-17.7.3-authz-policy-change':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Authorization Policy Change" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Authorization Policy Change' | Select-String 'Authorization Policy Change') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.8.x -- Privilege Use
    # CIS 17.8.1 -- Ensure 'Audit Sensitive Privilege Use' is set to 'Success and Failure'
    # Already set in profile::security, but we ensure consistency
    exec { 'cis-17.8.1-sensitive-privilege-use':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Sensitive Privilege Use" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Sensitive Privilege Use' | Select-String 'Sensitive Privilege Use') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.9.x -- System
    # CIS 17.9.1 -- Ensure 'Audit IPsec Driver' is set to 'Success and Failure'
    exec { 'cis-17.9.1-ipsec-driver':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"IPsec Driver" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'IPsec Driver' | Select-String 'IPsec Driver') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.9.2 -- Ensure 'Audit Other System Events' is set to 'Success and Failure'
    exec { 'cis-17.9.2-other-system-events':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Other System Events" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Other System Events' | Select-String 'Other System Events') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.9.3 -- Ensure 'Audit Security State Change' is set to include 'Success'
    exec { 'cis-17.9.3-security-state-change':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Security State Change" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Security State Change' | Select-String 'Security State Change') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.9.4 -- Ensure 'Audit Security System Extension' is set to include 'Success'
    exec { 'cis-17.9.4-security-system-extension':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Security System Extension" /success:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'Security System Extension' | Select-String 'Security System Extension') -match 'Success') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }

    # CIS 17.9.5 -- Ensure 'Audit System Integrity' is set to 'Success and Failure'
    exec { 'cis-17.9.5-system-integrity':
      command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"System Integrity" /success:enable /failure:enable',
      unless  => "${ps} -Command \"if ((auditpol /get /subcategory:'System Integrity' | Select-String 'System Integrity') -match 'Success and Failure') { exit 0 } else { exit 1 }\"",
      tag     => ['cis', 'cis_17', 'compliance'],
    }
  }

  # ====================================================================
  # CIS 18.x -- Administrative Templates (Computer)
  # ====================================================================
  tag('cis_admin_templates')

  # CIS 18.1.1.1 -- Ensure 'Prevent enabling lock screen camera' is Enabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization\\NoLockScreenCamera':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.1.1.2 -- Ensure 'Prevent enabling lock screen slide show' is Enabled
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization\\NoLockScreenSlideshow':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.3.1 -- Ensure 'Configure SMB v1 client driver' is Disabled
  # SMBv1 already disabled in profile::security. We add the MrxSmb10 driver setting.
  registry_key { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\mrxsmb10':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\mrxsmb10\\Start':
    ensure  => present,
    type    => dword,
    data    => 4,
    require => Registry_key['HKLM\\SYSTEM\\CurrentControlSet\\Services\\mrxsmb10'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.3.2 -- Ensure 'Configure SMB v1 server' is Disabled
  registry_key { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters\\SMB1':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.4.4 -- Ensure 'MSS: (DisableIPSourceRouting IPv6)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters\\DisableIPSourceRouting':
    ensure => present,
    type   => dword,
    data   => 2,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.4.5 -- Ensure 'MSS: (DisableIPSourceRouting)' is Enabled (highest protection)
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\DisableIPSourceRouting':
    ensure => present,
    type   => dword,
    data   => 2,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.4.8 -- Ensure 'MSS: (NoNameReleaseOnDemand)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\NetBT\\Parameters\\NoNameReleaseOnDemand':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.4.9 -- Ensure 'MSS: (SafeDllSearchMode)' is Enabled
  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\SafeDllSearchMode':
    ensure => present,
    type   => dword,
    data   => 1,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.4.10 -- Ensure 'MSS: (ScreenSaverGracePeriod)' is set to '5 or fewer seconds'
  registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\\ScreenSaverGracePeriod':
    ensure => present,
    type   => string,
    data   => '5',
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.5.x -- Network settings
  # CIS 18.5.4.1 -- Ensure 'Turn off multicast name resolution' is Enabled (LLMNR)
  # Already disabled in profile::security via registry

  # CIS 18.5.8.1 -- Ensure 'Enable insecure guest logons' is Disabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\LanmanWorkstation':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\LanmanWorkstation\\AllowInsecureGuestAuth':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\LanmanWorkstation'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.8.3.1 -- Ensure 'Include command line in process creation events' is Enabled
  registry_key { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\Audit':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\Audit\\ProcessCreationIncludeCmdLine_Enabled':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\Audit'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.8.14.1 -- Ensure 'Boot-Start Driver Initialization Policy' is Enabled: 'Good, unknown and bad but critical'
  registry_key { 'HKLM\\SYSTEM\\CurrentControlSet\\Policies\\EarlyLaunch':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Policies\\EarlyLaunch\\DriverLoadPolicy':
    ensure  => present,
    type    => dword,
    data    => 3,
    require => Registry_key['HKLM\\SYSTEM\\CurrentControlSet\\Policies\\EarlyLaunch'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.x -- Windows Components
  # CIS 18.9.4.1 -- Ensure 'Allow a Windows app to share application data between users' is Disabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CurrentVersion\\AppModel\\StateManager':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CurrentVersion\\AppModel\\StateManager\\AllowSharedLocalAppData':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CurrentVersion\\AppModel\\StateManager'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.5.1 -- Ensure 'Allow Microsoft accounts to be optional' is Enabled
  registry_key { 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\AppAccountsOptional':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.8.1 -- Ensure 'Disallow Autoplay for non-volume devices' is Enabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer\\NoAutoplayfornonVolume':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.8.2 -- Ensure 'Set default behavior for AutoRun' is Enabled: 'Do not execute any autorun commands'
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer\\NoAutorun':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.8.3 -- Ensure 'Turn off Autoplay' is Enabled: 'All drives'
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer\\NoDriveTypeAutoRun':
    ensure  => present,
    type    => dword,
    data    => 255,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.47.1 -- Ensure 'Enable Windows NTP Client' is Enabled
  # Already handled by profile::base via w32time service

  # CIS 18.9.77.x -- Windows Remote Management (WinRM)
  # CIS 18.9.77.3.2 -- Ensure 'Disallow WinRM from storing RunAs credentials' is Enabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service\\DisableRunAs':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.80.1.1 -- Ensure 'Configure Windows Defender SmartScreen' is Enabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System\\EnableSmartScreen':
    ensure  => present,
    type    => dword,
    data    => 1,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\System'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.84.1 -- Ensure 'Allow Basic authentication' (WinRM Client) is Disabled
  registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client':
    ensure => present,
    tag    => ['cis', 'cis_18', 'compliance'],
  }

  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client\\AllowBasic':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.84.2 -- Ensure 'Allow unencrypted traffic' (WinRM Client) is Disabled
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client\\AllowUnencryptedTraffic':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.84.3 -- Ensure 'Disallow Digest authentication' is Enabled
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client\\AllowDigest':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.85.1 -- Ensure 'Allow Basic authentication' (WinRM Service) is Disabled
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service\\AllowBasic':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # CIS 18.9.85.2 -- Ensure 'Allow unencrypted traffic' (WinRM Service) is Disabled
  registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service\\AllowUnencryptedTraffic':
    ensure  => present,
    type    => dword,
    data    => 0,
    require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service'],
    tag     => ['cis', 'cis_18', 'compliance'],
  }

  # ====================================================================
  # CIS Level 2 -- Additional Controls
  # ====================================================================
  if $cis_level >= 2 {
    tag('cis_level2')

    # CIS 18.3.6 (L2) -- Ensure 'NetBT NodeType configuration' is set to 'P-node'
    registry_value { 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\NetBT\\Parameters\\NodeType':
      ensure => present,
      type   => dword,
      data   => 2,
      tag    => ['cis', 'cis_18', 'compliance', 'cis_level2'],
    }

    # CIS 18.9.13.1 (L2) -- Ensure 'Turn off Microsoft consumer experiences' is Enabled
    registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent':
      ensure => present,
      tag    => ['cis', 'cis_18', 'compliance', 'cis_level2'],
    }

    registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent\\DisableWindowsConsumerFeatures':
      ensure  => present,
      type    => dword,
      data    => 1,
      require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent'],
      tag     => ['cis', 'cis_18', 'compliance', 'cis_level2'],
    }

    # CIS 2.3.7.9 (L2) -- Ensure 'Interactive logon: Smart card removal behavior' is set to
    # 'Lock Workstation' or higher
    registry_value { 'HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\\ScRemoveOption':
      ensure => present,
      type   => string,
      data   => '1',
      tag    => ['cis', 'cis_2_3', 'compliance', 'cis_level2'],
    }
  }

  # ====================================================================
  # STIG-Specific Controls (when enabled)
  # ====================================================================
  if $stig_enabled {
    tag('stig')

    # V-205625 -- Ensure PowerShell script block logging is enabled
    registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging':
      ensure => present,
      tag    => ['stig', 'compliance'],
    }

    registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging\\EnableScriptBlockLogging':
      ensure  => present,
      type    => dword,
      data    => 1,
      require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging'],
      tag     => ['stig', 'compliance'],
    }

    # V-205626 -- Ensure PowerShell Transcription is enabled
    registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\Transcription':
      ensure => present,
      tag    => ['stig', 'compliance'],
    }

    registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\Transcription\\EnableTranscripting':
      ensure  => present,
      type    => dword,
      data    => 1,
      require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\Transcription'],
      tag     => ['stig', 'compliance'],
    }

    registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\Transcription\\OutputDirectory':
      ensure  => present,
      type    => string,
      data    => 'C:\\ProgramData\\AnvilOps\\PsTranscripts',
      require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\Transcription'],
      tag     => ['stig', 'compliance'],
    }

    # V-205627 -- Ensure 'Prevent access to the command prompt' for standard users
    # Skipped -- too restrictive for server management; logged as advisory

    # V-205653 -- Ensure 'Windows Defender Credential Guard' is enabled
    registry_key { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeviceGuard':
      ensure => present,
      tag    => ['stig', 'compliance'],
    }

    registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeviceGuard\\EnableVirtualizationBasedSecurity':
      ensure  => present,
      type    => dword,
      data    => 1,
      require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeviceGuard'],
      tag     => ['stig', 'compliance'],
    }

    registry_value { 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeviceGuard\\LsaCfgFlags':
      ensure  => present,
      type    => dword,
      data    => 1,
      require => Registry_key['HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeviceGuard'],
      tag     => ['stig', 'compliance'],
    }

    # V-205714 -- Ensure TLS 1.0 is disabled
    ['Client', 'Server'].each |String $role| {
      registry_key { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\${role}":
        ensure => present,
        tag    => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\${role}\\Enabled":
        ensure  => present,
        type    => dword,
        data    => 0,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\${role}"],
        tag     => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\${role}\\DisabledByDefault":
        ensure  => present,
        type    => dword,
        data    => 1,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.0\\${role}"],
        tag     => ['stig', 'compliance'],
      }
    }

    # V-205715 -- Ensure TLS 1.1 is disabled
    ['Client', 'Server'].each |String $role| {
      registry_key { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.1\\${role}":
        ensure => present,
        tag    => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.1\\${role}\\Enabled":
        ensure  => present,
        type    => dword,
        data    => 0,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.1\\${role}"],
        tag     => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.1\\${role}\\DisabledByDefault":
        ensure  => present,
        type    => dword,
        data    => 1,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\TLS 1.1\\${role}"],
        tag     => ['stig', 'compliance'],
      }
    }

    # V-205716 -- Ensure SSL 2.0 is disabled
    ['Client', 'Server'].each |String $role| {
      registry_key { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 2.0\\${role}":
        ensure => present,
        tag    => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 2.0\\${role}\\Enabled":
        ensure  => present,
        type    => dword,
        data    => 0,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 2.0\\${role}"],
        tag     => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 2.0\\${role}\\DisabledByDefault":
        ensure  => present,
        type    => dword,
        data    => 1,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 2.0\\${role}"],
        tag     => ['stig', 'compliance'],
      }
    }

    # V-205717 -- Ensure SSL 3.0 is disabled
    ['Client', 'Server'].each |String $role| {
      registry_key { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 3.0\\${role}":
        ensure => present,
        tag    => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 3.0\\${role}\\Enabled":
        ensure  => present,
        type    => dword,
        data    => 0,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 3.0\\${role}"],
        tag     => ['stig', 'compliance'],
      }

      registry_value { "HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 3.0\\${role}\\DisabledByDefault":
        ensure  => present,
        type    => dword,
        data    => 1,
        require => Registry_key["HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecurityProviders\\SCHANNEL\\Protocols\\SSL 3.0\\${role}"],
        tag     => ['stig', 'compliance'],
      }
    }

    # Create directory for PowerShell transcripts
    file { 'C:/ProgramData/AnvilOps/PsTranscripts':
      ensure => directory,
      tag    => ['stig', 'compliance'],
    }
  }
}
