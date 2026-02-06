# @summary Manages host-based firewall rules
#
# This profile manages host-based firewall configuration for both Linux (firewalld)
# and Windows Firewall, including default policies and allowed services/ports.
#
# @param allowed_services_linux
#   Array of firewalld service names to allow (e.g., ['ssh', 'http'])
# @param allowed_ports
#   Hash of ports to allow (format: { 'port/protocol' => 'description' })
# @param default_deny
#   Whether to set default policy to deny (drop)
# @param windows_firewall_profiles
#   Hash of Windows Firewall profiles to enable/disable
# @param vpc_cidr
#   VPC CIDR range to allow for internal communication
#
# @example Basic usage
#   include profile::firewall
#
# @example Custom rules
#   class { 'profile::firewall':
#     allowed_services_linux => ['ssh', 'http', 'https'],
#     allowed_ports          => {
#       '8080/tcp' => 'Application port',
#       '9090/tcp' => 'Metrics port',
#     },
#   }
#
class profile::firewall (
  Array[String] $allowed_services_linux     = ['ssh'],
  Hash          $allowed_ports              = {},
  Boolean       $default_deny               = true,
  Hash          $windows_firewall_profiles  = {
    'Domain'  => true,
    'Private' => true,
    'Public'  => true,
  },
  String        $vpc_cidr                   = '10.0.0.0/8',
) {
  case $facts['os']['family'] {
    'RedHat', 'Debian': {
      # Ensure firewalld is installed and running
      package { 'firewalld':
        ensure => installed,
      }

      service { 'firewalld':
        ensure  => running,
        enable  => true,
        require => Package['firewalld'],
      }

      # Set default zone behavior
      if $default_deny {
        exec { 'firewalld-set-default-zone-drop':
          command => '/usr/bin/firewall-cmd --set-default-zone=drop',
          unless  => '/usr/bin/firewall-cmd --get-default-zone | /usr/bin/grep -q "^drop$"',
          require => Service['firewalld'],
        }
      }

      # Allow specified services
      $allowed_services_linux.each |$service| {
        exec { "firewalld-allow-service-${service}":
          command => "/usr/bin/firewall-cmd --permanent --add-service=${service} && /usr/bin/firewall-cmd --reload",
          unless  => "/usr/bin/firewall-cmd --list-services | /usr/bin/grep -qw ${service}",
          require => Service['firewalld'],
        }
      }

      # Allow specified ports
      $allowed_ports.each |$port, $description| {
        exec { "firewalld-allow-port-${port}":
          command => "/usr/bin/firewall-cmd --permanent --add-port=${port} && /usr/bin/firewall-cmd --reload",
          unless  => "/usr/bin/firewall-cmd --list-ports | /usr/bin/grep -qw ${port}",
          require => Service['firewalld'],
        }
      }

      # Allow ICMP echo from VPC CIDR
      exec { 'firewalld-allow-icmp-from-vpc':
        command => "/usr/bin/firewall-cmd --permanent --add-rich-rule='rule family=\"ipv4\" source address=\"${vpc_cidr}\" icmp-block-inversion accept' && /usr/bin/firewall-cmd --reload",
        unless  => "/usr/bin/firewall-cmd --list-rich-rules | /usr/bin/grep -q 'source address=\"${vpc_cidr}\"'",
        require => Service['firewalld'],
      }
    }

    'windows': {
      # Manage Windows Firewall profiles (Domain, Private, Public)
      $windows_firewall_profiles.each |$profile_name, $enabled| {
        exec { "windows-firewall-profile-${profile_name}":
          command => "C:/Windows/System32/netsh.exe advfirewall set ${profile_name}profile state ${enabled ? { true => 'on', false => 'off' }}",
          unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"(Get-NetFirewallProfile -Name ${profile_name}).Enabled -eq \$${enabled}\"",
        }
      }

      # Allow specified ports via Windows Firewall rules
      $allowed_ports.each |$port, $description| {
        # Parse port and protocol (e.g., "8080/tcp")
        $port_parts = split($port, '/')
        $port_number = $port_parts[0]
        $protocol = $port_parts[1]

        exec { "windows-firewall-allow-${port}":
          command => "C:/Windows/System32/netsh.exe advfirewall firewall add rule name=\"AnvilOps: ${description}\" dir=in action=allow protocol=${protocol} localport=${port_number}",
          unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"Get-NetFirewallRule -DisplayName 'AnvilOps: ${description}' -ErrorAction SilentlyContinue\"",
        }
      }

      # Allow ICMP echo (ping) from VPC CIDR
      exec { 'windows-firewall-allow-icmp':
        command => "C:/Windows/System32/netsh.exe advfirewall firewall add rule name=\"AnvilOps: Allow ICMP Echo\" protocol=icmpv4:8,any dir=in action=allow remoteip=${vpc_cidr}",
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"Get-NetFirewallRule -DisplayName 'AnvilOps: Allow ICMP Echo' -ErrorAction SilentlyContinue\"",
      }

      # Allow RDP by default on Windows (port 3389)
      exec { 'windows-firewall-allow-rdp':
        command => 'C:/Windows/System32/netsh.exe advfirewall firewall add rule name="AnvilOps: Remote Desktop" dir=in action=allow protocol=tcp localport=3389',
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"Get-NetFirewallRule -DisplayName 'AnvilOps: Remote Desktop' -ErrorAction SilentlyContinue\"",
      }

      # Allow WinRM for Ansible (ports 5985, 5986)
      exec { 'windows-firewall-allow-winrm-http':
        command => 'C:/Windows/System32/netsh.exe advfirewall firewall add rule name="AnvilOps: WinRM HTTP" dir=in action=allow protocol=tcp localport=5985',
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"Get-NetFirewallRule -DisplayName 'AnvilOps: WinRM HTTP' -ErrorAction SilentlyContinue\"",
      }

      exec { 'windows-firewall-allow-winrm-https':
        command => 'C:/Windows/System32/netsh.exe advfirewall firewall add rule name="AnvilOps: WinRM HTTPS" dir=in action=allow protocol=tcp localport=5986',
        unless  => "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \"Get-NetFirewallRule -DisplayName 'AnvilOps: WinRM HTTPS' -ErrorAction SilentlyContinue\"",
      }
    }

    default: {
      fail("Unsupported operating system family: ${facts['os']['family']}")
    }
  }
}
