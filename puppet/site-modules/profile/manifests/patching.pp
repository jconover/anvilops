# @summary Configures automated patching policies
#
# This profile manages OS patching configuration for both Linux and Windows
# systems, including patch scheduling, categories, and reboot behavior.
#
# @param patch_window
#   When to apply patches (e.g., 'Sunday 02:00')
# @param auto_reboot
#   Whether to automatically reboot after patching
# @param patch_categories_windows
#   Windows Update categories to install
# @param auto_update_security_linux
#   Whether to automatically install security updates on Linux
#
# @example Basic usage
#   include profile::patching
#
# @example Custom patch window
#   class { 'profile::patching':
#     patch_window => 'Saturday 03:00',
#     auto_reboot  => true,
#   }
#
class profile::patching (
  String         $patch_window                = 'Sunday 02:00',
  Boolean        $auto_reboot                 = false,
  Array[String]  $patch_categories_windows    = ['SecurityUpdates', 'CriticalUpdates'],
  Boolean        $auto_update_security_linux  = true,
) {
  case $facts['os']['family'] {
    'RedHat': {
      # Handle RHEL/CentOS/Amazon Linux patching
      case $facts['os']['release']['major'] {
        '7': {
          # RHEL/CentOS 7 uses yum-cron
          package { 'yum-cron':
            ensure => installed,
          }

          file { '/etc/yum/yum-cron.conf':
            ensure  => file,
            owner   => 'root',
            group   => 'root',
            mode    => '0644',
            content => epp('profile/yum_cron.epp', {
              'auto_update_security' => $auto_update_security_linux,
              'auto_reboot'          => $auto_reboot,
            }),
            require => Package['yum-cron'],
            notify  => Service['yum-cron'],
          }

          service { 'yum-cron':
            ensure    => running,
            enable    => true,
            subscribe => File['/etc/yum/yum-cron.conf'],
            require   => Package['yum-cron'],
          }
        }
        default: {
          # RHEL/CentOS 8+ and Amazon Linux 2023 use dnf-automatic
          package { 'dnf-automatic':
            ensure => installed,
          }

          file { '/etc/dnf/automatic.conf':
            ensure  => file,
            owner   => 'root',
            group   => 'root',
            mode    => '0644',
            content => epp('profile/yum_cron.epp', {
              'auto_update_security' => $auto_update_security_linux,
              'auto_reboot'          => $auto_reboot,
            }),
            require => Package['dnf-automatic'],
            notify  => Service['dnf-automatic.timer'],
          }

          service { 'dnf-automatic.timer':
            ensure    => running,
            enable    => true,
            subscribe => File['/etc/dnf/automatic.conf'],
            require   => Package['dnf-automatic'],
          }
        }
      }
    }

    'Debian': {
      # Handle Ubuntu/Debian patching with unattended-upgrades
      package { 'unattended-upgrades':
        ensure => installed,
      }

      file { '/etc/apt/apt.conf.d/50unattended-upgrades':
        ensure  => file,
        owner   => 'root',
        group   => 'root',
        mode    => '0644',
        content => epp('profile/unattended_upgrades.epp', {
          'auto_update_security' => $auto_update_security_linux,
          'auto_reboot'          => $auto_reboot,
          'patch_window'         => $patch_window,
        }),
        require => Package['unattended-upgrades'],
      }

      file { '/etc/apt/apt.conf.d/20auto-upgrades':
        ensure  => file,
        owner   => 'root',
        group   => 'root',
        mode    => '0644',
        content => "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";\n",
        require => Package['unattended-upgrades'],
      }
    }

    'windows': {
      # Configure Windows Update settings via registry
      # AUOptions: 4 = Auto download and schedule install
      # ScheduledInstallDay: 0 = Every day, 1 = Sunday, 2 = Monday, etc.
      # ScheduledInstallTime: Hour of day (0-23)

      # Parse patch window to get day and time
      $day_mapping = {
        'Sunday'    => 1,
        'Monday'    => 2,
        'Tuesday'   => 3,
        'Wednesday' => 4,
        'Thursday'  => 5,
        'Friday'    => 6,
        'Saturday'  => 7,
      }

      # Extract day from patch_window (e.g., "Sunday 02:00")
      $patch_day_name = regsubst($patch_window, '^(\w+)\s+.*$', '\1')
      $patch_hour = Integer(regsubst($patch_window, '^\w+\s+(\d+):.*$', '\1'))
      $scheduled_install_day = $day_mapping[$patch_day_name]

      # Windows Update registry settings
      registry_key { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate':
        ensure => present,
      }

      registry_key { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU':
        ensure  => present,
        require => Registry_key['HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'],
      }

      # Configure automatic updates
      registry_value { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\AUOptions':
        ensure  => present,
        type    => dword,
        data    => 4,  # Auto download and schedule install
        require => Registry_key['HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'],
      }

      registry_value { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\ScheduledInstallDay':
        ensure  => present,
        type    => dword,
        data    => $scheduled_install_day,
        require => Registry_key['HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'],
      }

      registry_value { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\ScheduledInstallTime':
        ensure  => present,
        type    => dword,
        data    => $patch_hour,
        require => Registry_key['HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'],
      }

      # Configure auto-reboot behavior
      registry_value { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\NoAutoRebootWithLoggedOnUsers':
        ensure  => present,
        type    => dword,
        data    => $auto_reboot ? {
          true  => 0,  # Allow reboot even with users logged on
          false => 1,  # Don't reboot if users are logged on
        },
        require => Registry_key['HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'],
      }

      # Configure update categories
      $patch_categories_windows.each |$category| {
        # This would typically be managed via WSUS or Windows Update for Business
        # For standalone systems, we rely on default Windows Update behavior
      }
    }

    default: {
      fail("Unsupported operating system family: ${facts['os']['family']}")
    }
  }
}
