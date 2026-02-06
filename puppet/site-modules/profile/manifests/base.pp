# @summary Base profile for all AnvilOps-managed servers
#
# This profile manages fundamental configuration that applies to every server
# regardless of OS or role. It handles timezone, NTP, login banners, and
# ensures essential agents are running.
#
# @param timezone
#   System timezone to configure
# @param ntp_servers
#   Array of NTP server addresses. Defaults to AWS Time Sync Service.
# @param motd_message
#   Message of the day / login banner text
#
# @example Basic usage
#   include profile::base
#
# @example With custom timezone
#   class { 'profile::base':
#     timezone => 'America/New_York',
#   }
#
class profile::base (
  String $timezone         = 'UTC',
  Array[String] $ntp_servers = ['169.254.169.123'],
  String $motd_message     = 'This server is managed by AnvilOps and Puppet. Unauthorized changes will be reverted.',
) {
  # OS-specific configuration
  case $facts['os']['family'] {
    'windows': {
      # Set timezone on Windows
      exec { 'set-timezone':
        command => "tzutil.exe /s \"${timezone}\"",
        unless  => "tzutil.exe /g | Select-String -Pattern '${timezone}' -Quiet",
        path    => ['C:\Windows\System32'],
      }

      # Configure Windows Time service
      service { 'w32time':
        ensure => running,
        enable => true,
      }

      # Configure NTP servers
      registry_value { 'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters\NtpServer':
        ensure => present,
        type   => string,
        data   => join($ntp_servers.map |$server| { "${server},0x9" }, ' '),
        notify => Service['w32time'],
      }

      registry_value { 'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters\Type':
        ensure => present,
        type   => string,
        data   => 'NTP',
        notify => Service['w32time'],
      }

      # Set legal notice (login banner)
      registry_value { 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\LegalNoticeText':
        ensure => present,
        type   => string,
        data   => $motd_message,
      }

      registry_value { 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\LegalNoticeCaption':
        ensure => present,
        type   => string,
        data   => 'AnvilOps Managed Server',
      }

      # Ensure AnvilOps service account exists
      user { 'anvilops-svc':
        ensure   => present,
        comment  => 'AnvilOps Service Account',
        groups   => ['Administrators'],
        password => Sensitive('*'), # Disabled password - use key-based auth
      }

      # Ensure SSM Agent is running (pre-installed on AWS Windows AMIs)
      service { 'AmazonSSMAgent':
        ensure => running,
        enable => true,
      }
    }
    'RedHat', 'Debian': {
      # Set timezone on Linux
      file { '/etc/localtime':
        ensure => link,
        target => "/usr/share/zoneinfo/${timezone}",
      }

      # Install and configure chrony for NTP
      package { 'chrony':
        ensure => installed,
      }

      file { '/etc/chrony.conf':
        ensure  => file,
        content => epp('profile/chrony.conf.epp', {
          'ntp_servers' => $ntp_servers,
        }),
        require => Package['chrony'],
        notify  => Service['chronyd'],
      }

      service { 'chronyd':
        ensure  => running,
        enable  => true,
        require => Package['chrony'],
      }

      # Manage MOTD
      file { '/etc/motd':
        ensure  => file,
        content => "${motd_message}\n",
        mode    => '0644',
      }

      # Create AnvilOps service account with sudo access
      user { 'anvilops-svc':
        ensure     => present,
        comment    => 'AnvilOps Service Account',
        home       => '/home/anvilops-svc',
        managehome => true,
        shell      => '/bin/bash',
      }

      file { '/etc/sudoers.d/anvilops-svc':
        ensure  => file,
        content => "anvilops-svc ALL=(ALL) NOPASSWD: ALL\n",
        mode    => '0440',
        require => User['anvilops-svc'],
      }

      # Ensure SSM Agent is running (pre-installed on AWS Linux AMIs)
      service { 'amazon-ssm-agent':
        ensure => running,
        enable => true,
      }
    }
    default: {
      fail("Unsupported OS family: ${facts['os']['family']}")
    }
  }
}
