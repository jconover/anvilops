# @summary Linux CIS Benchmark compliance enforcement
#
# Implements the most impactful CIS controls for RHEL/CentOS/Amazon Linux
# and Debian/Ubuntu, covering filesystem hardening, network stack security,
# access control, logging, and authentication. Controls are mapped to
# specific CIS Benchmark section numbers for audit traceability.
#
# This class is NOT intended to implement all 300+ CIS controls. It focuses
# on the highest-impact, most commonly audited controls that provide real
# security value in an AWS environment managed by AnvilOps.
#
# @param cis_level CIS benchmark level (1 or 2)
# @param stig_enabled Whether to apply additional STIG controls
# @param report_only Whether to run in audit-only mode
# @param enforce_file_permissions Whether to enforce file permission controls
# @param enforce_network_hardening Whether to enforce network sysctl controls
# @param enforce_audit_rules Whether to deploy comprehensive audit rules
#
# @example
#   include profile::compliance::linux
#
class profile::compliance::linux (
  Integer[1,2] $cis_level                = 1,
  Boolean      $stig_enabled             = false,
  Boolean      $report_only              = false,
  Boolean      $enforce_file_permissions  = true,
  Boolean      $enforce_network_hardening = true,
  Boolean      $enforce_audit_rules      = true,
) {
  # Fail fast on non-Linux
  if $facts['os']['family'] !~ /^(RedHat|Debian)$/ {
    fail("profile::compliance::linux can only be applied to Linux systems, not ${facts['os']['family']}")
  }

  # ====================================================================
  # CIS 1.1.x -- Filesystem Configuration
  # Disable mounting of uncommon/dangerous filesystem types
  # ====================================================================
  tag('cis_filesystem')

  # The existing profile::security already disables cramfs, freevxfs, jffs2,
  # hfs, hfsplus, and udf. We add squashfs and fat (vfat) here, plus ensure
  # the /tmp, /var/tmp partitions have noexec,nosuid,nodev if separate.

  $disabled_filesystems_level1 = ['squashfs', 'vfat']

  $disabled_filesystems_level1.each |String $fs| {
    file_line { "cis-disable-fs-${fs}":
      ensure => present,
      path   => '/etc/modprobe.d/anvilops-cis-filesystems.conf',
      line   => "install ${fs} /bin/true",
      match  => "^install ${fs}",
      tag    => ['cis', 'cis_1_1', 'compliance'],
    }
  }

  # Ensure the modprobe config file exists with correct permissions
  file { '/etc/modprobe.d/anvilops-cis-filesystems.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    tag    => ['cis', 'cis_1_1', 'compliance'],
  }

  # CIS 1.1.2-1.1.5 -- Secure /tmp mount options
  # Only apply if /tmp is a separate mount (common on AWS AMIs with cloud-init)
  if $facts['mountpoints'] and $facts['mountpoints']['/tmp'] {
    file_line { 'cis-tmp-noexec':
      ensure => present,
      path   => '/etc/fstab',
      match  => '^\S+\s+/tmp\s+',
      line   => "tmpfs /tmp tmpfs defaults,nodev,nosuid,noexec 0 0",
      tag    => ['cis', 'cis_1_1', 'compliance'],
    }
  }

  # CIS 1.1.21 -- Ensure sticky bit is set on all world-writable directories
  # Scheduled check rather than continuous enforcement to avoid performance impact
  exec { 'cis-sticky-bit-world-writable':
    command => '/usr/bin/find / -xdev -type d \( -perm -0002 -a ! -perm -1000 \) -exec chmod a+t {} \;',
    onlyif  => '/usr/bin/test $(/usr/bin/find / -xdev -type d \( -perm -0002 -a ! -perm -1000 \) 2>/dev/null | /usr/bin/wc -l) -gt 0',
    tag     => ['cis', 'cis_1_1', 'compliance'],
  }

  # ====================================================================
  # CIS 1.3.x -- Filesystem Integrity Checking (AIDE)
  # ====================================================================
  tag('cis_integrity')

  $aide_package = $facts['os']['family'] ? {
    'RedHat' => 'aide',
    'Debian' => 'aide',
  }

  package { $aide_package:
    ensure => installed,
    tag    => ['cis', 'cis_1_3', 'compliance'],
  }

  # Initialize AIDE database if it does not exist
  exec { 'cis-aide-init':
    command => '/usr/sbin/aide --init && /bin/cp /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz',
    creates => '/var/lib/aide/aide.db.gz',
    require => Package[$aide_package],
    tag     => ['cis', 'cis_1_3', 'compliance'],
  }

  # CIS 1.3.2 -- Ensure filesystem integrity is regularly checked
  file { '/etc/cron.d/anvilops-aide-check':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "# AnvilOps CIS 1.3.2 -- AIDE integrity check\n0 5 * * * root /usr/sbin/aide --check --config /etc/aide.conf 2>&1 | /usr/bin/logger -t aide-check\n",
    require => Package[$aide_package],
    tag     => ['cis', 'cis_1_3', 'compliance'],
  }

  # ====================================================================
  # CIS 1.4.x -- Secure Boot Settings
  # ====================================================================
  tag('cis_boot')

  # CIS 1.4.1 -- Ensure permissions on bootloader config are configured
  $grub_cfg = $facts['os']['family'] ? {
    'RedHat' => '/boot/grub2/grub.cfg',
    'Debian' => '/boot/grub/grub.cfg',
  }

  file { $grub_cfg:
    mode => '0600',
    tag  => ['cis', 'cis_1_4', 'compliance'],
  }

  # CIS 1.4.3 -- Ensure authentication required for single user mode
  # On systemd systems, set root password for emergency/rescue targets
  if $facts['service_provider'] == 'systemd' {
    file_line { 'cis-rescue-sulogin':
      ensure => present,
      path   => '/usr/lib/systemd/system/rescue.service',
      match  => '^ExecStart=',
      line   => 'ExecStart=-/usr/lib/systemd/systemd-sulogin-shell rescue',
      tag    => ['cis', 'cis_1_4', 'compliance'],
    }

    file_line { 'cis-emergency-sulogin':
      ensure => present,
      path   => '/usr/lib/systemd/system/emergency.service',
      match  => '^ExecStart=',
      line   => 'ExecStart=-/usr/lib/systemd/systemd-sulogin-shell emergency',
      tag    => ['cis', 'cis_1_4', 'compliance'],
    }
  }

  # ====================================================================
  # CIS 1.5.x -- Additional Process Hardening
  # ====================================================================
  tag('cis_process')

  # CIS 1.5.1 -- Ensure core dumps are restricted
  file_line { 'cis-limits-core-dump':
    ensure => present,
    path   => '/etc/security/limits.conf',
    line   => '* hard core 0',
    match  => '^\*.*hard.*core',
    tag    => ['cis', 'cis_1_5', 'compliance'],
  }

  sysctl { 'fs.suid_dumpable':
    ensure => present,
    value  => '0',
    tag    => ['cis', 'cis_1_5', 'compliance'],
  }

  # CIS 1.5.3 -- Ensure ASLR is enabled (defense against buffer overflow)
  sysctl { 'kernel.randomize_va_space':
    ensure => present,
    value  => '2',
    tag    => ['cis', 'cis_1_5', 'compliance'],
  }

  # ====================================================================
  # CIS 3.x -- Network Configuration
  # ====================================================================
  if $enforce_network_hardening {
    tag('cis_network')

    # CIS 3.1.1 -- Ensure IP forwarding is disabled
    sysctl { 'net.ipv4.ip_forward':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_1', 'compliance'],
    }

    # CIS 3.1.2 -- Ensure packet redirect sending is disabled
    sysctl { 'net.ipv4.conf.all.send_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_1', 'compliance'],
    }

    sysctl { 'net.ipv4.conf.default.send_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_1', 'compliance'],
    }

    # CIS 3.2.1 -- Ensure source routed packets are not accepted
    sysctl { 'net.ipv4.conf.all.accept_source_route':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    sysctl { 'net.ipv4.conf.default.accept_source_route':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.2 -- Ensure ICMP redirects are not accepted
    sysctl { 'net.ipv4.conf.all.accept_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    sysctl { 'net.ipv4.conf.default.accept_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.3 -- Ensure secure ICMP redirects are not accepted
    sysctl { 'net.ipv4.conf.all.secure_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    sysctl { 'net.ipv4.conf.default.secure_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.4 -- Ensure suspicious packets are logged
    sysctl { 'net.ipv4.conf.all.log_martians':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    sysctl { 'net.ipv4.conf.default.log_martians':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.5 -- Ensure broadcast ICMP requests are ignored
    sysctl { 'net.ipv4.icmp_echo_ignore_broadcasts':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.6 -- Ensure bogus ICMP responses are ignored
    sysctl { 'net.ipv4.icmp_ignore_bogus_error_responses':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.7 -- Ensure Reverse Path Filtering is enabled
    sysctl { 'net.ipv4.conf.all.rp_filter':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    sysctl { 'net.ipv4.conf.default.rp_filter':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.2.8 -- Ensure TCP SYN Cookies is enabled
    sysctl { 'net.ipv4.tcp_syncookies':
      ensure => present,
      value  => '1',
      tag    => ['cis', 'cis_3_2', 'compliance'],
    }

    # CIS 3.3.x -- IPv6 hardening (disable if not needed in AWS)
    sysctl { 'net.ipv6.conf.all.accept_ra':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_3', 'compliance'],
    }

    sysctl { 'net.ipv6.conf.default.accept_ra':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_3', 'compliance'],
    }

    sysctl { 'net.ipv6.conf.all.accept_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_3', 'compliance'],
    }

    sysctl { 'net.ipv6.conf.default.accept_redirects':
      ensure => present,
      value  => '0',
      tag    => ['cis', 'cis_3_3', 'compliance'],
    }

    # CIS Level 2 -- Additional network hardening
    if $cis_level >= 2 {
      # Disable IPv6 entirely (Level 2)
      sysctl { 'net.ipv6.conf.all.disable_ipv6':
        ensure => present,
        value  => '1',
        tag    => ['cis', 'cis_3_3', 'compliance', 'cis_level2'],
      }

      sysctl { 'net.ipv6.conf.default.disable_ipv6':
        ensure => present,
        value  => '1',
        tag    => ['cis', 'cis_3_3', 'compliance', 'cis_level2'],
      }

      # Disable DCCP protocol
      file_line { 'cis-disable-dccp':
        ensure => present,
        path   => '/etc/modprobe.d/anvilops-cis-filesystems.conf',
        line   => 'install dccp /bin/true',
        match  => '^install dccp',
        tag    => ['cis', 'cis_3_4', 'compliance', 'cis_level2'],
      }

      # Disable SCTP protocol
      file_line { 'cis-disable-sctp':
        ensure => present,
        path   => '/etc/modprobe.d/anvilops-cis-filesystems.conf',
        line   => 'install sctp /bin/true',
        match  => '^install sctp',
        tag    => ['cis', 'cis_3_4', 'compliance', 'cis_level2'],
      }

      # Disable RDS protocol
      file_line { 'cis-disable-rds':
        ensure => present,
        path   => '/etc/modprobe.d/anvilops-cis-filesystems.conf',
        line   => 'install rds /bin/true',
        match  => '^install rds',
        tag    => ['cis', 'cis_3_4', 'compliance', 'cis_level2'],
      }

      # Disable TIPC protocol
      file_line { 'cis-disable-tipc':
        ensure => present,
        path   => '/etc/modprobe.d/anvilops-cis-filesystems.conf',
        line   => 'install tipc /bin/true',
        match  => '^install tipc',
        tag    => ['cis', 'cis_3_4', 'compliance', 'cis_level2'],
      }
    }
  }

  # ====================================================================
  # CIS 4.x -- Logging and Auditing
  # ====================================================================
  if $enforce_audit_rules {
    tag('cis_audit')

    # Ensure auditd is installed and running (the package/service are
    # already declared in profile::security; we manage the rules file here)
    # Note: profile::security declares Package['audit'] and Service['auditd']

    # Create the AnvilOps CIS audit rules file
    file { '/etc/audit/rules.d/anvilops-cis.rules':
      ensure  => file,
      owner   => 'root',
      group   => 'root',
      mode    => '0640',
      tag     => ['cis', 'cis_4_1', 'compliance'],
      require => Package['audit'],
      notify  => Exec['cis-reload-audit-rules'],
    }

    # CIS 4.1.3 -- Ensure changes to system administration scope are collected
    profile::compliance::audit_rule { 'cis-4.1.3-sudoers':
      rule  => '-w /etc/sudoers -p wa -k scope',
      order => 10,
    }

    profile::compliance::audit_rule { 'cis-4.1.3-sudoers.d':
      rule  => '-w /etc/sudoers.d/ -p wa -k scope',
      order => 11,
    }

    # CIS 4.1.4 -- Ensure login and logout events are collected
    profile::compliance::audit_rule { 'cis-4.1.4-faillog':
      rule  => '-w /var/log/faillog -p wa -k logins',
      order => 20,
    }

    profile::compliance::audit_rule { 'cis-4.1.4-lastlog':
      rule  => '-w /var/log/lastlog -p wa -k logins',
      order => 21,
    }

    profile::compliance::audit_rule { 'cis-4.1.4-tallylog':
      rule  => '-w /var/log/tallylog -p wa -k logins',
      order => 22,
    }

    # CIS 4.1.5 -- Ensure session initiation information is collected
    profile::compliance::audit_rule { 'cis-4.1.5-utmp':
      rule  => '-w /var/run/utmp -p wa -k session',
      order => 30,
    }

    profile::compliance::audit_rule { 'cis-4.1.5-wtmp':
      rule  => '-w /var/log/wtmp -p wa -k session',
      order => 31,
    }

    profile::compliance::audit_rule { 'cis-4.1.5-btmp':
      rule  => '-w /var/log/btmp -p wa -k session',
      order => 32,
    }

    # CIS 4.1.6 -- Ensure events that modify date and time are collected
    profile::compliance::audit_rule { 'cis-4.1.6-time-adjtimex-64':
      rule  => '-a always,exit -F arch=b64 -S adjtimex -S settimeofday -k time-change',
      order => 40,
    }

    profile::compliance::audit_rule { 'cis-4.1.6-time-adjtimex-32':
      rule  => '-a always,exit -F arch=b32 -S adjtimex -S settimeofday -S stime -k time-change',
      order => 41,
    }

    profile::compliance::audit_rule { 'cis-4.1.6-time-clock-settime-64':
      rule  => '-a always,exit -F arch=b64 -S clock_settime -k time-change',
      order => 42,
    }

    profile::compliance::audit_rule { 'cis-4.1.6-time-clock-settime-32':
      rule  => '-a always,exit -F arch=b32 -S clock_settime -k time-change',
      order => 43,
    }

    profile::compliance::audit_rule { 'cis-4.1.6-time-localtime':
      rule  => '-w /etc/localtime -p wa -k time-change',
      order => 44,
    }

    # CIS 4.1.7 -- Ensure events that modify user/group information are collected
    profile::compliance::audit_rule { 'cis-4.1.7-identity-group':
      rule  => '-w /etc/group -p wa -k identity',
      order => 50,
    }

    profile::compliance::audit_rule { 'cis-4.1.7-identity-passwd':
      rule  => '-w /etc/passwd -p wa -k identity',
      order => 51,
    }

    profile::compliance::audit_rule { 'cis-4.1.7-identity-gshadow':
      rule  => '-w /etc/gshadow -p wa -k identity',
      order => 52,
    }

    profile::compliance::audit_rule { 'cis-4.1.7-identity-shadow':
      rule  => '-w /etc/shadow -p wa -k identity',
      order => 53,
    }

    profile::compliance::audit_rule { 'cis-4.1.7-identity-opasswd':
      rule  => '-w /etc/security/opasswd -p wa -k identity',
      order => 54,
    }

    # CIS 4.1.8 -- Ensure events that modify the network environment are collected
    profile::compliance::audit_rule { 'cis-4.1.8-network-sethostname-64':
      rule  => '-a always,exit -F arch=b64 -S sethostname -S setdomainname -k system-locale',
      order => 60,
    }

    profile::compliance::audit_rule { 'cis-4.1.8-network-sethostname-32':
      rule  => '-a always,exit -F arch=b32 -S sethostname -S setdomainname -k system-locale',
      order => 61,
    }

    profile::compliance::audit_rule { 'cis-4.1.8-network-issue':
      rule  => '-w /etc/issue -p wa -k system-locale',
      order => 62,
    }

    profile::compliance::audit_rule { 'cis-4.1.8-network-issue-net':
      rule  => '-w /etc/issue.net -p wa -k system-locale',
      order => 63,
    }

    profile::compliance::audit_rule { 'cis-4.1.8-network-hosts':
      rule  => '-w /etc/hosts -p wa -k system-locale',
      order => 64,
    }

    profile::compliance::audit_rule { 'cis-4.1.8-network-sysconfig':
      rule  => '-w /etc/sysconfig/network -p wa -k system-locale',
      order => 65,
    }

    # CIS 4.1.9 -- Ensure discretionary access control permission modification events are collected
    profile::compliance::audit_rule { 'cis-4.1.9-perm-mod-chmod-64':
      rule  => '-a always,exit -F arch=b64 -S chmod -S fchmod -S fchmodat -F auid>=1000 -F auid!=4294967295 -k perm_mod',
      order => 70,
    }

    profile::compliance::audit_rule { 'cis-4.1.9-perm-mod-chmod-32':
      rule  => '-a always,exit -F arch=b32 -S chmod -S fchmod -S fchmodat -F auid>=1000 -F auid!=4294967295 -k perm_mod',
      order => 71,
    }

    profile::compliance::audit_rule { 'cis-4.1.9-perm-mod-chown-64':
      rule  => '-a always,exit -F arch=b64 -S chown -S fchown -S fchownat -S lchown -F auid>=1000 -F auid!=4294967295 -k perm_mod',
      order => 72,
    }

    profile::compliance::audit_rule { 'cis-4.1.9-perm-mod-chown-32':
      rule  => '-a always,exit -F arch=b32 -S chown -S fchown -S fchownat -S lchown -F auid>=1000 -F auid!=4294967295 -k perm_mod',
      order => 73,
    }

    profile::compliance::audit_rule { 'cis-4.1.9-perm-mod-setxattr-64':
      rule  => '-a always,exit -F arch=b64 -S setxattr -S lsetxattr -S fsetxattr -S removexattr -S lremovexattr -S fremovexattr -F auid>=1000 -F auid!=4294967295 -k perm_mod',
      order => 74,
    }

    profile::compliance::audit_rule { 'cis-4.1.9-perm-mod-setxattr-32':
      rule  => '-a always,exit -F arch=b32 -S setxattr -S lsetxattr -S fsetxattr -S removexattr -S lremovexattr -S fremovexattr -F auid>=1000 -F auid!=4294967295 -k perm_mod',
      order => 75,
    }

    # CIS 4.1.10 -- Ensure unsuccessful unauthorized file access attempts are collected
    profile::compliance::audit_rule { 'cis-4.1.10-access-64':
      rule  => '-a always,exit -F arch=b64 -S creat -S open -S openat -S truncate -S ftruncate -F exit=-EACCES -F auid>=1000 -F auid!=4294967295 -k access',
      order => 80,
    }

    profile::compliance::audit_rule { 'cis-4.1.10-access-32':
      rule  => '-a always,exit -F arch=b32 -S creat -S open -S openat -S truncate -S ftruncate -F exit=-EACCES -F auid>=1000 -F auid!=4294967295 -k access',
      order => 81,
    }

    profile::compliance::audit_rule { 'cis-4.1.10-access-eperm-64':
      rule  => '-a always,exit -F arch=b64 -S creat -S open -S openat -S truncate -S ftruncate -F exit=-EPERM -F auid>=1000 -F auid!=4294967295 -k access',
      order => 82,
    }

    profile::compliance::audit_rule { 'cis-4.1.10-access-eperm-32':
      rule  => '-a always,exit -F arch=b32 -S creat -S open -S openat -S truncate -S ftruncate -F exit=-EPERM -F auid>=1000 -F auid!=4294967295 -k access',
      order => 83,
    }

    # CIS 4.1.14 -- Ensure file deletion events by users are collected
    profile::compliance::audit_rule { 'cis-4.1.14-delete-64':
      rule  => '-a always,exit -F arch=b64 -S unlink -S unlinkat -S rename -S renameat -F auid>=1000 -F auid!=4294967295 -k delete',
      order => 90,
    }

    profile::compliance::audit_rule { 'cis-4.1.14-delete-32':
      rule  => '-a always,exit -F arch=b32 -S unlink -S unlinkat -S rename -S renameat -F auid>=1000 -F auid!=4294967295 -k delete',
      order => 91,
    }

    # CIS 4.1.15 -- Ensure kernel module loading and unloading is collected
    profile::compliance::audit_rule { 'cis-4.1.15-modules-insmod':
      rule  => '-w /sbin/insmod -p x -k modules',
      order => 100,
    }

    profile::compliance::audit_rule { 'cis-4.1.15-modules-rmmod':
      rule  => '-w /sbin/rmmod -p x -k modules',
      order => 101,
    }

    profile::compliance::audit_rule { 'cis-4.1.15-modules-modprobe':
      rule  => '-w /sbin/modprobe -p x -k modules',
      order => 102,
    }

    profile::compliance::audit_rule { 'cis-4.1.15-modules-init-64':
      rule  => '-a always,exit -F arch=b64 -S init_module -S delete_module -k modules',
      order => 103,
    }

    # CIS 4.1.17 -- Ensure the audit configuration is immutable
    # This MUST be the last rule loaded
    profile::compliance::audit_rule { 'cis-4.1.17-immutable':
      rule  => '-e 2',
      order => 999,
    }

    # Reload audit rules when changed
    exec { 'cis-reload-audit-rules':
      command     => '/sbin/augenrules --load',
      refreshonly => true,
      tag         => ['cis', 'cis_4_1', 'compliance'],
    }

    # CIS 4.2.x -- Ensure rsyslog/journald is configured
    # CIS 4.2.1.1 -- Ensure rsyslog is installed
    $syslog_package = $facts['os']['family'] ? {
      'RedHat' => 'rsyslog',
      'Debian' => 'rsyslog',
    }

    package { $syslog_package:
      ensure => installed,
      tag    => ['cis', 'cis_4_2', 'compliance'],
    }

    service { 'rsyslog':
      ensure  => running,
      enable  => true,
      require => Package[$syslog_package],
      tag     => ['cis', 'cis_4_2', 'compliance'],
    }

    # CIS 4.2.1.3 -- Ensure rsyslog default file permissions configured
    file_line { 'cis-rsyslog-file-create-mode':
      ensure  => present,
      path    => '/etc/rsyslog.conf',
      line    => '$FileCreateMode 0640',
      match   => '^\$FileCreateMode',
      require => Package[$syslog_package],
      notify  => Service['rsyslog'],
      tag     => ['cis', 'cis_4_2', 'compliance'],
    }
  }

  # ====================================================================
  # CIS 5.x -- Access, Authentication, and Authorization
  # ====================================================================
  tag('cis_access')

  # CIS 5.1.x -- Cron configuration
  # CIS 5.1.2 -- Ensure permissions on /etc/crontab
  file { '/etc/crontab':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0600',
    tag    => ['cis', 'cis_5_1', 'compliance'],
  }

  # CIS 5.1.3-5.1.7 -- Cron directory permissions
  ['/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly', '/etc/cron.monthly', '/etc/cron.d'].each |String $cron_dir| {
    file { $cron_dir:
      ensure => directory,
      owner  => 'root',
      group  => 'root',
      mode   => '0700',
      tag    => ['cis', 'cis_5_1', 'compliance'],
    }
  }

  # CIS 5.1.8 -- Ensure at/cron is restricted to authorized users
  file { '/etc/cron.allow':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    content => "root\n",
    tag     => ['cis', 'cis_5_1', 'compliance'],
  }

  file { '/etc/cron.deny':
    ensure => absent,
    tag    => ['cis', 'cis_5_1', 'compliance'],
  }

  file { '/etc/at.allow':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    content => "root\n",
    tag     => ['cis', 'cis_5_1', 'compliance'],
  }

  file { '/etc/at.deny':
    ensure => absent,
    tag    => ['cis', 'cis_5_1', 'compliance'],
  }

  # CIS 5.2.x -- SSH Server Configuration
  # Most SSH hardening is already in profile::security via the sshd_config template.
  # We add the controls not already covered:

  # CIS 5.2.11 -- Ensure SSH MaxAuthTries is set to 4 or less
  # Already set to 3 in profile::security

  # CIS 5.2.12 -- Ensure SSH Idle Timeout Interval is configured
  # Already set in sshd_config.epp (ClientAliveInterval 300, ClientAliveCountMax 2)

  # CIS 5.2.15 -- Ensure SSH warning banner is configured
  # Already set in sshd_config.epp (Banner /etc/issue.net)

  # Ensure the warning banner file exists with compliant content
  file { '/etc/issue.net':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "Authorized uses only. All activity may be monitored and reported.\n",
    tag     => ['cis', 'cis_5_2', 'compliance'],
  }

  file { '/etc/issue':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "Authorized uses only. All activity may be monitored and reported.\n",
    tag     => ['cis', 'cis_5_2', 'compliance'],
  }

  # CIS 5.3.x -- PAM Configuration
  # CIS 5.3.1 -- Ensure password creation requirements are configured
  $pam_pwquality_package = $facts['os']['family'] ? {
    'RedHat' => 'libpwquality',
    'Debian' => 'libpam-pwquality',
  }

  package { $pam_pwquality_package:
    ensure => installed,
    tag    => ['cis', 'cis_5_3', 'compliance'],
  }

  file { '/etc/security/pwquality.conf':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => @("PWQUALITY")
      # AnvilOps CIS 5.3.1 -- Password Quality Requirements
      # Managed by Puppet -- DO NOT EDIT MANUALLY
      minlen = 14
      dcredit = -1
      ucredit = -1
      ocredit = -1
      lcredit = -1
      minclass = 4
      maxrepeat = 3
      maxclassrepeat = 3
      | PWQUALITY
    require => Package[$pam_pwquality_package],
    tag     => ['cis', 'cis_5_3', 'compliance'],
  }

  # CIS 5.3.3 -- Ensure password reuse is limited (remember last 5 passwords)
  file_line { 'cis-pam-password-reuse':
    ensure => present,
    path   => '/etc/pam.d/system-auth',
    line   => 'password    sufficient    pam_unix.so sha512 shadow try_first_pass use_authtok remember=5',
    match  => '^password\s+sufficient\s+pam_unix\.so',
    tag    => ['cis', 'cis_5_3', 'compliance'],
  }

  # CIS 5.4.x -- User Accounts and Environment
  # CIS 5.4.1.1-5.4.1.3 -- Password expiration (already in profile::security via login.defs)

  # CIS 5.4.1.4 -- Ensure inactive password lock is 30 days or less
  exec { 'cis-useradd-inactive':
    command => '/usr/sbin/useradd -D -f 30',
    unless  => '/usr/sbin/useradd -D | /usr/bin/grep -q "INACTIVE=30"',
    tag     => ['cis', 'cis_5_4', 'compliance'],
  }

  # CIS 5.4.4 -- Ensure default user umask is 027 or more restrictive
  # Already configured in profile::linux_base

  # CIS 5.4.5 -- Ensure default user shell timeout is 900 seconds or less
  file_line { 'cis-shell-timeout-profile':
    ensure => present,
    path   => '/etc/profile',
    line   => 'readonly TMOUT=900 ; export TMOUT',
    match  => '^(readonly\s+)?TMOUT=',
    tag    => ['cis', 'cis_5_4', 'compliance'],
  }

  # ====================================================================
  # CIS 6.x -- System Maintenance
  # ====================================================================
  if $enforce_file_permissions {
    tag('cis_maintenance')

    # CIS 6.1.2-6.1.9 -- File permission enforcement on critical files
    # Note: /etc/passwd, /etc/shadow, /etc/group, /etc/gshadow are already
    # managed by profile::security. We enforce the remaining ones here.

    file { '/etc/passwd-':
      ensure => file,
      owner  => 'root',
      group  => 'root',
      mode   => '0600',
      tag    => ['cis', 'cis_6_1', 'compliance'],
    }

    file { '/etc/shadow-':
      ensure => file,
      owner  => 'root',
      group  => 'root',
      mode   => '0600',
      tag    => ['cis', 'cis_6_1', 'compliance'],
    }

    file { '/etc/group-':
      ensure => file,
      owner  => 'root',
      group  => 'root',
      mode   => '0600',
      tag    => ['cis', 'cis_6_1', 'compliance'],
    }

    file { '/etc/gshadow-':
      ensure => file,
      owner  => 'root',
      group  => 'root',
      mode   => '0600',
      tag    => ['cis', 'cis_6_1', 'compliance'],
    }

    # CIS 6.2.x -- User and Group Settings
    # CIS 6.2.1 -- Ensure password fields are not empty
    exec { 'cis-check-empty-passwords':
      command  => '/usr/bin/logger -t anvilops-compliance "CIS 6.2.1 FAIL: Accounts with empty passwords found"',
      onlyif   => '/usr/bin/awk -F: \'($2 == "") {found=1} END {exit !found}\' /etc/shadow',
      tag      => ['cis', 'cis_6_2', 'compliance'],
      loglevel => 'warning',
    }

    # CIS 6.2.6 -- Ensure root PATH integrity
    exec { 'cis-check-root-path':
      command  => '/usr/bin/logger -t anvilops-compliance "CIS 6.2.6 FAIL: Root PATH contains writable or group-writable directories"',
      onlyif   => '/usr/bin/test -n "$(/usr/bin/echo "$PATH" | /usr/bin/tr ":" "\n" | while read dir; do [ -d "$dir" ] && [ "$(/usr/bin/stat -c %a "$dir" 2>/dev/null)" != "755" ] && echo "$dir"; done)"',
      tag      => ['cis', 'cis_6_2', 'compliance'],
      loglevel => 'warning',
    }
  }

  # ====================================================================
  # STIG-Specific Controls (when enabled)
  # ====================================================================
  if $stig_enabled {
    tag('stig')

    # V-230223 -- Ensure FIPS mode is enabled
    exec { 'stig-fips-check':
      command  => '/usr/bin/logger -t anvilops-compliance "STIG V-230223: FIPS mode is not enabled"',
      unless   => '/usr/bin/test "$(/usr/bin/cat /proc/sys/crypto/fips_enabled 2>/dev/null)" = "1"',
      tag      => ['stig', 'compliance'],
      loglevel => 'warning',
    }

    # V-230231 -- Ensure crypto policy is not set to legacy
    exec { 'stig-crypto-policy':
      command => '/usr/bin/update-crypto-policies --set DEFAULT',
      unless  => '/usr/bin/update-crypto-policies --show | /usr/bin/grep -qE "^(DEFAULT|FUTURE|FIPS)$"',
      tag     => ['stig', 'compliance'],
    }

    # V-230264 -- Ensure all accounts have a password or are locked
    exec { 'stig-lock-passwordless-accounts':
      command => '/usr/bin/awk -F: \'($2 == "!" || $2 == "!!") && $1 != "root" {print $1}\' /etc/shadow | while read user; do /usr/sbin/usermod -L "$user" 2>/dev/null; done',
      onlyif  => '/usr/bin/awk -F: \'($2 == "!" || $2 == "!!") && $1 != "root" && $1 !~ /^(nfsnobody|nobody)$/ {found=1} END {exit !found}\' /etc/shadow',
      tag     => ['stig', 'compliance'],
    }

    # V-230324 -- Ensure /var/log/messages permissions
    file { '/var/log/messages':
      mode => '0640',
      tag  => ['stig', 'compliance'],
    }

    # V-230330 -- Ensure audit tools have correct permissions
    ['/usr/sbin/auditctl', '/usr/sbin/aureport', '/usr/sbin/ausearch', '/usr/sbin/autrace', '/usr/sbin/auditd', '/usr/sbin/augenrules'].each |String $audit_tool| {
      file { $audit_tool:
        mode => '0755',
        tag  => ['stig', 'compliance'],
      }
    }
  }
}
