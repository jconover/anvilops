# @summary Linux-specific base configuration
#
# This profile manages Linux-specific base configuration including essential
# packages, sysctl settings, umask, and basic SSH hardening.
#
# @param base_packages
#   Array of essential packages to install on all Linux servers
# @param sysctl_settings
#   Hash of sysctl kernel parameters to manage
# @param umask
#   Default umask value for system-wide file creation
#
# @example Basic usage
#   include profile::linux_base
#
# @example With custom packages and sysctl
#   class { 'profile::linux_base':
#     base_packages   => ['curl', 'vim', 'htop', 'nc'],
#     sysctl_settings => {
#       'net.ipv4.tcp_syncookies' => 1,
#       'kernel.randomize_va_space' => 2,
#     },
#   }
#
class profile::linux_base (
  Array[String] $base_packages = ['curl', 'wget', 'vim', 'htop', 'jq', 'unzip', 'git'],
  Hash $sysctl_settings        = {
    'net.ipv4.tcp_syncookies'       => 1,
    'net.ipv4.conf.all.rp_filter'   => 1,
    'net.ipv4.conf.all.accept_source_route' => 0,
    'net.ipv4.conf.all.accept_redirects'    => 0,
    'net.ipv4.conf.all.secure_redirects'    => 0,
    'net.ipv4.conf.all.send_redirects'      => 0,
    'net.ipv4.icmp_echo_ignore_broadcasts'  => 1,
    'kernel.randomize_va_space'     => 2,
  },
  String $umask                = '027',
) {
  # Fail fast if not Linux
  if $facts['os']['family'] !~ /^(RedHat|Debian)$/ {
    fail("profile::linux_base can only be applied to Linux systems, not ${facts['os']['family']}")
  }

  # Ensure base packages are installed
  ensure_packages($base_packages, {
    'ensure' => 'installed',
  })

  # Manage sysctl settings
  $sysctl_settings.each |String $key, Variant[String, Integer] $value| {
    sysctl { $key:
      ensure => present,
      value  => String($value),
    }
  }

  # Set system-wide umask
  file_line { 'umask-profile':
    ensure => present,
    path   => '/etc/profile',
    line   => "umask ${umask}",
    match  => '^umask\s+\d+',
  }

  file_line { 'umask-bashrc':
    ensure => present,
    path   => '/etc/bashrc',
    line   => "umask ${umask}",
    match  => '^umask\s+\d+',
  }

  # Basic SSH daemon configuration (not full hardening)
  file { '/etc/ssh/sshd_config.d/anvilops.conf':
    ensure  => file,
    content => epp('profile/sshd_anvilops.conf.epp'),
    mode    => '0600',
    notify  => Service['sshd'],
  }

  service { 'sshd':
    ensure => running,
    enable => true,
  }

  # Ensure logging is configured
  case $facts['os']['family'] {
    'RedHat': {
      # RHEL/CentOS/Amazon Linux - check for systemd
      if $facts['service_provider'] == 'systemd' {
        # Using systemd-journald
        service { 'systemd-journald':
          ensure => running,
          enable => true,
        }

        # Ensure persistent journal storage
        file { '/var/log/journal':
          ensure => directory,
          mode   => '2755',
          owner  => 'root',
          group  => 'systemd-journal',
        }
      } else {
        # Using rsyslog
        package { 'rsyslog':
          ensure => installed,
        }

        service { 'rsyslog':
          ensure  => running,
          enable  => true,
          require => Package['rsyslog'],
        }
      }
    }
    'Debian': {
      # Ubuntu/Debian - typically uses systemd
      if $facts['service_provider'] == 'systemd' {
        service { 'systemd-journald':
          ensure => running,
          enable => true,
        }

        file { '/var/log/journal':
          ensure => directory,
          mode   => '2755',
          owner  => 'root',
          group  => 'systemd-journal',
        }
      } else {
        package { 'rsyslog':
          ensure => installed,
        }

        service { 'rsyslog':
          ensure  => running,
          enable  => true,
          require => Package['rsyslog'],
        }
      }
    }
    default: {
      # Do nothing for other OS families
    }
  }

  # Set hostname from metadata
  if $facts['ec2_metadata'] {
    $hostname = pick($facts['ec2_metadata']['tags']['Name'], $facts['networking']['hostname'])

    file { '/etc/hostname':
      ensure  => file,
      content => "${hostname}\n",
    }

    exec { 'set-hostname':
      command => "/usr/bin/hostnamectl set-hostname ${hostname}",
      unless  => "/usr/bin/hostnamectl status | /usr/bin/grep 'Static hostname: ${hostname}'",
      require => File['/etc/hostname'],
    }
  }
}
