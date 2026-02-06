# @summary Manages CloudWatch agent for metrics and log collection
#
# This profile manages the Amazon CloudWatch agent on both Linux and Windows
# systems, collecting system metrics (CPU, memory, disk, network) and logs.
#
# @param agent_version
#   Version of CloudWatch agent to install (default: 'latest')
# @param log_group_prefix
#   CloudWatch Logs group prefix for this environment
# @param metrics_collection_interval
#   Interval in seconds for metrics collection
# @param log_retention_days
#   Number of days to retain CloudWatch Logs
#
# @example Basic usage
#   include profile::monitoring
#
# @example Custom configuration
#   class { 'profile::monitoring':
#     metrics_collection_interval => 300,
#     log_retention_days          => 90,
#   }
#
class profile::monitoring (
  String  $agent_version                = 'latest',
  String  $log_group_prefix             = '/anvilops',
  Integer $metrics_collection_interval  = 60,
  Integer $log_retention_days           = 30,
) {
  # Determine OS-specific paths and package names
  case $facts['os']['family'] {
    'RedHat', 'Debian': {
      $config_path = '/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json'
      $config_dir  = '/opt/aws/amazon-cloudwatch-agent/etc'
      $service_name = 'amazon-cloudwatch-agent'
      $package_name = 'amazon-cloudwatch-agent'

      # Ensure CloudWatch agent package is installed (Linux)
      package { $package_name:
        ensure => $agent_version ? {
          'latest' => 'latest',
          default  => $agent_version,
        },
      }

      # Ensure config directory exists
      file { $config_dir:
        ensure  => directory,
        owner   => 'root',
        group   => 'root',
        mode    => '0755',
        require => Package[$package_name],
      }

      # Deploy CloudWatch agent configuration (Linux)
      file { $config_path:
        ensure  => file,
        owner   => 'root',
        group   => 'root',
        mode    => '0644',
        content => epp('profile/cloudwatch_config_linux.epp', {
          'log_group_prefix'             => $log_group_prefix,
          'metrics_collection_interval'  => $metrics_collection_interval,
          'hostname'                     => $facts['networking']['fqdn'],
        }),
        require => File[$config_dir],
        notify  => Service[$service_name],
      }

      # Ensure CloudWatch agent service is running
      service { $service_name:
        ensure    => running,
        enable    => true,
        subscribe => File[$config_path],
        require   => Package[$package_name],
      }
    }

    'windows': {
      $config_path = 'C:/ProgramData/Amazon/AmazonCloudWatchAgent/amazon-cloudwatch-agent.json'
      $config_dir  = 'C:/ProgramData/Amazon/AmazonCloudWatchAgent'
      $service_name = 'AmazonCloudWatchAgent'
      $package_name = 'amazon-cloudwatch-agent'

      # Ensure CloudWatch agent package is installed (Windows via Chocolatey)
      package { $package_name:
        ensure   => $agent_version ? {
          'latest' => 'latest',
          default  => $agent_version,
        },
        provider => 'chocolatey',
      }

      # Ensure config directory exists
      file { $config_dir:
        ensure  => directory,
        require => Package[$package_name],
      }

      # Deploy CloudWatch agent configuration (Windows)
      file { $config_path:
        ensure  => file,
        content => epp('profile/cloudwatch_config_windows.epp', {
          'log_group_prefix'             => $log_group_prefix,
          'metrics_collection_interval'  => $metrics_collection_interval,
          'hostname'                     => $facts['networking']['fqdn'],
        }),
        require => File[$config_dir],
        notify  => Service[$service_name],
      }

      # Ensure CloudWatch agent service is running
      service { $service_name:
        ensure    => running,
        enable    => true,
        subscribe => File[$config_path],
        require   => Package[$package_name],
      }
    }

    default: {
      fail("Unsupported operating system family: ${facts['os']['family']}")
    }
  }
}
