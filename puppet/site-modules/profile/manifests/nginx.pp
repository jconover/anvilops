# @summary Nginx web server profile for Linux
#
# This profile installs and configures Nginx web server with sensible defaults
# for production use. It manages the package, configuration, service, and firewall.
#
# @param manage_repo
#   Whether to manage the Nginx package repository (recommended for latest stable)
# @param worker_processes
#   Number of worker processes (use 'auto' for CPU core count)
# @param worker_connections
#   Maximum number of simultaneous connections per worker
# @param default_site_root
#   Document root for the default site
# @param client_max_body_size
#   Maximum allowed size of client request body
#
# @example Basic usage
#   include profile::nginx
#
# @example With custom settings
#   class { 'profile::nginx':
#     worker_processes => 4,
#     client_max_body_size => '50M',
#   }
#
class profile::nginx (
  Boolean $manage_repo = true,
  Variant[Integer[1], Enum['auto']] $worker_processes = 'auto',
  Integer[1] $worker_connections = 1024,
  String $default_site_root = '/var/www/html',
  String $client_max_body_size = '10M',
) {
  # Fail fast if not Linux
  if $facts['os']['family'] !~ /^(RedHat|Debian)$/ {
    fail("profile::nginx can only be applied to Linux systems, not ${facts['os']['family']}")
  }

  # Manage Nginx repository for latest stable version
  if $manage_repo {
    case $facts['os']['family'] {
      'RedHat': {
        yumrepo { 'nginx':
          descr    => 'nginx repo',
          baseurl  => "http://nginx.org/packages/rhel/${facts['os']['release']['major']}/\$basearch/",
          gpgcheck => 1,
          enabled  => 1,
          gpgkey   => 'https://nginx.org/keys/nginx_signing.key',
          before   => Package['nginx'],
        }
      }
      'Debian': {
        # For Debian/Ubuntu, use apt repository
        ensure_packages(['apt-transport-https', 'ca-certificates'], {
          'ensure' => 'installed',
          'before' => Exec['add-nginx-key'],
        })

        exec { 'add-nginx-key':
          command => '/usr/bin/wget -qO - https://nginx.org/keys/nginx_signing.key | /usr/bin/apt-key add -',
          unless  => '/usr/bin/apt-key list | /bin/grep -q nginx',
          before  => File['/etc/apt/sources.list.d/nginx.list'],
        }

        file { '/etc/apt/sources.list.d/nginx.list':
          ensure  => file,
          content => "deb http://nginx.org/packages/${facts['os']['distro']['id'].downcase}/ ${facts['os']['distro']['codename']} nginx\n",
          before  => Exec['apt-update-nginx'],
        }

        exec { 'apt-update-nginx':
          command     => '/usr/bin/apt-get update',
          refreshonly => true,
          subscribe   => File['/etc/apt/sources.list.d/nginx.list'],
          before      => Package['nginx'],
        }
      }
      default: {
        # Do nothing
      }
    }
  }

  # Install Nginx
  package { 'nginx':
    ensure => installed,
  }

  # Create document root
  file { $default_site_root:
    ensure => directory,
    owner  => 'nginx',
    group  => 'nginx',
    mode   => '0755',
  }

  # Manage main nginx.conf
  file { '/etc/nginx/nginx.conf':
    ensure  => file,
    content => epp('profile/nginx.conf.epp', {
      'worker_processes'      => $worker_processes,
      'worker_connections'    => $worker_connections,
      'client_max_body_size'  => $client_max_body_size,
    }),
    require => Package['nginx'],
    notify  => Service['nginx'],
  }

  # Manage default site configuration
  file { '/etc/nginx/conf.d/default.conf':
    ensure  => file,
    content => epp('profile/nginx_default_site.conf.epp', {
      'default_site_root' => $default_site_root,
    }),
    require => Package['nginx'],
    notify  => Service['nginx'],
  }

  # Create a simple index page
  file { "${default_site_root}/index.html":
    ensure  => file,
    content => epp('profile/nginx_index.html.epp', {
      'hostname' => $facts['networking']['fqdn'],
    }),
    owner   => 'nginx',
    group   => 'nginx',
    mode    => '0644',
    require => File[$default_site_root],
  }

  # Ensure Nginx service is running
  service { 'nginx':
    ensure  => running,
    enable  => true,
    require => Package['nginx'],
  }

  # Open firewall ports
  case $facts['os']['family'] {
    'RedHat': {
      # Use firewalld on RHEL/CentOS 7+
      if $facts['os']['release']['major'] >= '7' {
        exec { 'firewalld-allow-http':
          command => '/usr/bin/firewall-cmd --permanent --add-service=http && /usr/bin/firewall-cmd --reload',
          unless  => '/usr/bin/firewall-cmd --list-services | /usr/bin/grep -qw http',
        }

        exec { 'firewalld-allow-https':
          command => '/usr/bin/firewall-cmd --permanent --add-service=https && /usr/bin/firewall-cmd --reload',
          unless  => '/usr/bin/firewall-cmd --list-services | /usr/bin/grep -qw https',
        }
      } else {
        # Use iptables for older systems
        exec { 'iptables-allow-http':
          command => '/sbin/iptables -I INPUT -p tcp --dport 80 -j ACCEPT && /sbin/service iptables save',
          unless  => '/sbin/iptables -L INPUT -n | /bin/grep -q "dpt:80"',
        }

        exec { 'iptables-allow-https':
          command => '/sbin/iptables -I INPUT -p tcp --dport 443 -j ACCEPT && /sbin/service iptables save',
          unless  => '/sbin/iptables -L INPUT -n | /bin/grep -q "dpt:443"',
        }
      }
    }
    'Debian': {
      # Use ufw on Ubuntu/Debian
      ensure_packages(['ufw'], {
        'ensure' => 'installed',
      })

      exec { 'ufw-allow-http':
        command => '/usr/sbin/ufw allow http',
        unless  => '/usr/sbin/ufw status | /bin/grep -qw "80/tcp"',
        require => Package['ufw'],
      }

      exec { 'ufw-allow-https':
        command => '/usr/sbin/ufw allow https',
        unless  => '/usr/sbin/ufw status | /bin/grep -qw "443/tcp"',
        require => Package['ufw'],
      }

      exec { 'ufw-enable':
        command => '/usr/sbin/ufw --force enable',
        unless  => '/usr/sbin/ufw status | /bin/grep -q "Status: active"',
        require => Package['ufw'],
      }
    }
    default: {
      # Do nothing
    }
  }
}
