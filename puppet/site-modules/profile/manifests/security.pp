# @summary CIS/STIG-inspired security baseline enforcement
#
# This profile implements security hardening based on CIS benchmarks and STIG
# guidelines for both Linux and Windows systems.
#
# @param ssh_permit_root_login
#   Whether to allow root login via SSH (Linux)
# @param ssh_password_auth
#   Whether to allow password authentication via SSH (Linux)
# @param ssh_max_auth_tries
#   Maximum authentication attempts before disconnecting (Linux)
# @param password_min_length
#   Minimum password length (Windows)
# @param password_max_age_days
#   Maximum password age in days (Windows)
# @param account_lockout_threshold
#   Failed login attempts before lockout (Windows)
# @param account_lockout_duration
#   Account lockout duration in minutes (Windows)
# @param disable_usb_storage
#   Whether to disable USB storage devices
# @param enable_audit_logging
#   Whether to enable comprehensive audit logging
#
# @example Basic usage
#   include profile::security
#
# @example Custom SSH security
#   class { 'profile::security':
#     ssh_permit_root_login => true,
#     ssh_max_auth_tries    => 5,
#   }
#
class profile::security (
  # Linux SSH settings
  Boolean $ssh_permit_root_login     = false,
  Boolean $ssh_password_auth         = false,
  Integer $ssh_max_auth_tries        = 3,
  # Windows password policy
  Integer $password_min_length       = 14,
  Integer $password_max_age_days     = 90,
  Integer $account_lockout_threshold = 5,
  Integer $account_lockout_duration  = 30,
  # General
  Boolean $disable_usb_storage       = false,
  Boolean $enable_audit_logging      = true,
) {
  case $facts['os']['family'] {
    'RedHat', 'Debian': {
      # Manage SSH daemon configuration
      package { 'openssh-server':
        ensure => installed,
      }

      file { '/etc/ssh/sshd_config':
        ensure  => file,
        owner   => 'root',
        group   => 'root',
        mode    => '0600',
        content => epp('profile/sshd_config.epp', {
          'permit_root_login' => $ssh_permit_root_login,
          'password_auth'     => $ssh_password_auth,
          'max_auth_tries'    => $ssh_max_auth_tries,
        }),
        require => Package['openssh-server'],
        notify  => Service['sshd'],
      }

      service { 'sshd':
        ensure    => running,
        enable    => true,
        subscribe => File['/etc/ssh/sshd_config'],
        require   => Package['openssh-server'],
      }

      # Manage auditd for security logging
      if $enable_audit_logging {
        package { 'audit':
          ensure => installed,
        }

        service { 'auditd':
          ensure  => running,
          enable  => true,
          require => Package['audit'],
        }

        # Add basic audit rules
        file { '/etc/audit/rules.d/anvilops-security.rules':
          ensure  => file,
          owner   => 'root',
          group   => 'root',
          mode    => '0640',
          content => @(AUDITRULES)
            # AnvilOps Security Audit Rules
            # Monitor changes to system time
            -a always,exit -F arch=b64 -S adjtimex -S settimeofday -k time-change
            -a always,exit -F arch=b32 -S adjtimex -S settimeofday -S stime -k time-change

            # Monitor user/group changes
            -w /etc/group -p wa -k identity
            -w /etc/passwd -p wa -k identity
            -w /etc/gshadow -p wa -k identity
            -w /etc/shadow -p wa -k identity

            # Monitor network environment changes
            -a always,exit -F arch=b64 -S sethostname -S setdomainname -k network-change
            -a always,exit -F arch=b32 -S sethostname -S setdomainname -k network-change

            # Monitor login/logout events
            -w /var/log/lastlog -p wa -k logins
            -w /var/run/faillock/ -p wa -k logins

            # Monitor sudo usage
            -w /etc/sudoers -p wa -k sudoers
            -w /etc/sudoers.d/ -p wa -k sudoers

            # Monitor privileged commands
            -a always,exit -F path=/usr/bin/sudo -F perm=x -F auid>=1000 -F auid!=4294967295 -k privileged
            | AUDITRULES
          require => Package['audit'],
          notify  => Exec['reload-auditd-rules'],
        }

        exec { 'reload-auditd-rules':
          command     => '/sbin/augenrules --load',
          refreshonly => true,
          require     => File['/etc/audit/rules.d/anvilops-security.rules'],
        }
      }

      # Disable unused filesystems
      file { '/etc/modprobe.d/anvilops-disable-filesystems.conf':
        ensure  => file,
        owner   => 'root',
        group   => 'root',
        mode    => '0644',
        content => @(MODPROBE)
          # AnvilOps: Disable unused filesystems
          install cramfs /bin/true
          install freevxfs /bin/true
          install jffs2 /bin/true
          install hfs /bin/true
          install hfsplus /bin/true
          install udf /bin/true
          | MODPROBE
      }

      # Disable USB storage if requested
      if $disable_usb_storage {
        file { '/etc/modprobe.d/anvilops-disable-usb-storage.conf':
          ensure  => file,
          owner   => 'root',
          group   => 'root',
          mode    => '0644',
          content => "install usb-storage /bin/true\n",
        }
      }

      # Set secure file permissions on critical files
      file { '/etc/passwd':
        ensure => file,
        owner  => 'root',
        group  => 'root',
        mode   => '0644',
      }

      file { '/etc/shadow':
        ensure => file,
        owner  => 'root',
        group  => 'root',
        mode   => '0000',
      }

      file { '/etc/group':
        ensure => file,
        owner  => 'root',
        group  => 'root',
        mode   => '0644',
      }

      file { '/etc/gshadow':
        ensure => file,
        owner  => 'root',
        group  => 'root',
        mode   => '0000',
      }

      # Configure password policy in login.defs
      file_line { 'login-defs-pass-max-days':
        ensure => present,
        path   => '/etc/login.defs',
        line   => 'PASS_MAX_DAYS 90',
        match  => '^PASS_MAX_DAYS',
      }

      file_line { 'login-defs-pass-min-days':
        ensure => present,
        path   => '/etc/login.defs',
        line   => 'PASS_MIN_DAYS 7',
        match  => '^PASS_MIN_DAYS',
      }

      file_line { 'login-defs-pass-warn-age':
        ensure => present,
        path   => '/etc/login.defs',
        line   => 'PASS_WARN_AGE 14',
        match  => '^PASS_WARN_AGE',
      }
    }

    'windows': {
      # Windows password policy via local security policy
      exec { 'windows-password-min-length':
        command => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"net accounts /minpwlen:${password_min_length}\"",
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"(net accounts | Select-String 'Minimum password length') -match '${password_min_length}'\"",
      }

      exec { 'windows-password-max-age':
        command => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"net accounts /maxpwage:${password_max_age_days}\"",
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"(net accounts | Select-String 'Maximum password age') -match '${password_max_age_days}'\"",
      }

      exec { 'windows-password-complexity':
        command => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "secedit /export /cfg $env:TEMP\\secpol.cfg; (Get-Content $env:TEMP\\secpol.cfg) -replace \'PasswordComplexity = 0\', \'PasswordComplexity = 1\' | Set-Content $env:TEMP\\secpol.cfg; secedit /configure /db $env:windir\\security\\local.sdb /cfg $env:TEMP\\secpol.cfg /areas SECURITYPOLICY; Remove-Item $env:TEMP\\secpol.cfg"',
        unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "(Get-ItemProperty -Path \'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters\' -Name \'RequireStrongKey\' -ErrorAction SilentlyContinue).RequireStrongKey -eq 1"',
      }

      exec { 'windows-account-lockout-threshold':
        command => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"net accounts /lockoutthreshold:${account_lockout_threshold}\"",
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"(net accounts | Select-String 'Lockout threshold') -match '${account_lockout_threshold}'\"",
      }

      exec { 'windows-account-lockout-duration':
        command => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"net accounts /lockoutduration:${account_lockout_duration}\"",
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"(net accounts | Select-String 'Lockout duration') -match '${account_lockout_duration}'\"",
      }

      # Disable SMBv1 (security vulnerability)
      exec { 'windows-disable-smbv1':
        command => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart"',
        unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "(Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol).State -eq \'Disabled\'"',
      }

      # Disable LLMNR (security vulnerability)
      registry_key { 'HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient':
        ensure => present,
      }

      registry_value { 'HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient\EnableMulticast':
        ensure  => present,
        type    => dword,
        data    => 0,
        require => Registry_key['HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient'],
      }

      # Disable NetBIOS over TCP/IP
      exec { 'windows-disable-netbios':
        command => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "Get-WmiObject Win32_NetworkAdapterConfiguration -Filter \'IPEnabled=True\' | ForEach-Object { $_.SetTcpipNetbios(2) }"',
        unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "$adapters = Get-WmiObject Win32_NetworkAdapterConfiguration -Filter \'IPEnabled=True\'; ($adapters | Where-Object { $_.TcpipNetbiosOptions -ne 2 }).Count -eq 0"',
      }

      # Disable Guest account
      exec { 'windows-disable-guest':
        command => 'C:/Windows/System32/net.exe user guest /active:no',
        unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "(Get-LocalUser -Name Guest).Enabled -eq $false"',
      }

      # Enable audit logging
      if $enable_audit_logging {
        # Enable audit policy for logon events
        exec { 'windows-audit-logon-events':
          command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Logon" /success:enable /failure:enable',
          unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "(auditpol /get /subcategory:\'Logon\' | Select-String \'Success and Failure\') -ne $null"',
        }

        # Enable audit policy for account management
        exec { 'windows-audit-account-management':
          command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"User Account Management" /success:enable /failure:enable',
          unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "(auditpol /get /subcategory:\'User Account Management\' | Select-String \'Success and Failure\') -ne $null"',
        }

        # Enable audit policy for privilege use
        exec { 'windows-audit-privilege-use':
          command => 'C:/Windows/System32/auditpol.exe /set /subcategory:"Sensitive Privilege Use" /success:enable /failure:enable',
          unless  => 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command "(auditpol /get /subcategory:\'Sensitive Privilege Use\' | Select-String \'Success and Failure\') -ne $null"',
        }
      }

      # Disable USB storage if requested
      if $disable_usb_storage {
        registry_key { 'HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR':
          ensure => present,
        }

        registry_value { 'HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR\Start':
          ensure  => present,
          type    => dword,
          data    => 4,  # Disabled
          require => Registry_key['HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR'],
        }
      }
    }

    default: {
      fail("Unsupported operating system family: ${facts['os']['family']}")
    }
  }
}
