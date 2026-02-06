# @summary Windows-specific base configuration
#
# This profile manages Windows-specific base configuration including RDP, WinRM,
# power settings, service hardening, and Chocolatey package manager.
#
# @param enable_rdp
#   Whether to enable Remote Desktop Protocol
# @param enable_winrm
#   Whether to enable WinRM over HTTPS
# @param power_plan
#   Windows power plan to activate
# @param disabled_services
#   Array of Windows services to disable for security/performance
#
# @example Basic usage
#   include profile::windows_base
#
# @example With custom settings
#   class { 'profile::windows_base':
#     enable_rdp        => false,
#     power_plan        => 'Balanced',
#     disabled_services => ['Spooler', 'XblGameSave'],
#   }
#
class profile::windows_base (
  Boolean $enable_rdp        = true,
  Boolean $enable_winrm      = true,
  String $power_plan         = 'High Performance',
  Array[String] $disabled_services = [
    'Spooler',          # Print Spooler (security risk if not needed)
    'XblGameSave',      # Xbox Live Game Save (not needed on servers)
    'XblAuthManager',   # Xbox Live Auth Manager (not needed on servers)
    'XboxNetApiSvc',    # Xbox Live Networking Service (not needed on servers)
  ],
) {
  # Fail fast if not Windows
  if $facts['os']['family'] != 'windows' {
    fail("profile::windows_base can only be applied to Windows systems, not ${facts['os']['family']}")
  }

  # Configure RDP
  if $enable_rdp {
    registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\fDenyTSConnections':
      ensure => present,
      type   => dword,
      data   => 0,
    }

    # Require Network Level Authentication (NLA) for security
    registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp\UserAuthentication':
      ensure => present,
      type   => dword,
      data   => 1,
    }

    # Allow RDP through Windows Firewall
    exec { 'enable-rdp-firewall':
      command => 'netsh.exe advfirewall firewall set rule group="remote desktop" new enable=Yes',
      unless  => 'netsh.exe advfirewall firewall show rule name=all | Select-String "Remote Desktop.*Enable.*Yes" -Quiet',
      path    => ['C:\Windows\System32'],
    }
  } else {
    registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\fDenyTSConnections':
      ensure => present,
      type   => dword,
      data   => 1,
    }

    exec { 'disable-rdp-firewall':
      command => 'netsh.exe advfirewall firewall set rule group="remote desktop" new enable=No',
      onlyif  => 'netsh.exe advfirewall firewall show rule name=all | Select-String "Remote Desktop.*Enable.*Yes" -Quiet',
      path    => ['C:\Windows\System32'],
    }
  }

  # Configure WinRM
  if $enable_winrm {
    service { 'WinRM':
      ensure => running,
      enable => true,
    }

    # Enable HTTPS listener (assuming certificate is already present)
    exec { 'winrm-enable-https':
      command => 'winrm.cmd quickconfig -transport:https -quiet',
      unless  => 'winrm.cmd enumerate winrm/config/listener | Select-String "Transport = HTTPS" -Quiet',
      path    => ['C:\Windows\System32'],
      require => Service['WinRM'],
    }

    # Allow WinRM through firewall
    exec { 'enable-winrm-firewall-http':
      command => 'netsh.exe advfirewall firewall add rule name="WinRM HTTP" dir=in action=allow protocol=TCP localport=5985',
      unless  => 'netsh.exe advfirewall firewall show rule name="WinRM HTTP" | Select-String "WinRM HTTP" -Quiet',
      path    => ['C:\Windows\System32'],
    }

    exec { 'enable-winrm-firewall-https':
      command => 'netsh.exe advfirewall firewall add rule name="WinRM HTTPS" dir=in action=allow protocol=TCP localport=5986',
      unless  => 'netsh.exe advfirewall firewall show rule name="WinRM HTTPS" | Select-String "WinRM HTTPS" -Quiet',
      path    => ['C:\Windows\System32'],
    }
  }

  # Set power plan
  exec { 'set-power-plan':
    command => "powercfg.exe /setactive SCHEME_MIN",
    unless  => "powercfg.exe /getactivescheme | Select-String '${power_plan}' -Quiet",
    path    => ['C:\Windows\System32'],
  }

  case $power_plan {
    'High Performance': {
      $power_guid = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
    }
    'Balanced': {
      $power_guid = '381b4222-f694-41f0-9685-ff5bb260df2e'
    }
    'Power Saver': {
      $power_guid = 'a1841308-3541-4fab-bc81-f71556f20b4a'
    }
    default: {
      $power_guid = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c' # Default to High Performance
    }
  }

  exec { "activate-power-plan-${power_plan}":
    command => "powercfg.exe /setactive ${power_guid}",
    unless  => "powercfg.exe /getactivescheme | Select-String '${power_guid}' -Quiet",
    path    => ['C:\Windows\System32'],
  }

  # Disable unnecessary services
  $disabled_services.each |String $service_name| {
    service { $service_name:
      ensure => stopped,
      enable => false,
    }
  }

  # Install Chocolatey package manager
  # Using the official Chocolatey Puppet module pattern
  class { 'chocolatey':
    chocolatey_download_url => 'https://community.chocolatey.org/api/v2/package/chocolatey',
    use_7zip                => false,
    log_output              => true,
  }

  # Configure system-managed pagefile
  registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PagingFiles':
    ensure => present,
    type   => multistring,
    data   => ['?:\pagefile.sys'], # System managed size
  }

  # Disable IPv6 if not needed (common best practice in AWS)
  registry_value { 'HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters\DisabledComponents':
    ensure => present,
    type   => dword,
    data   => 255, # Disable all IPv6 components
  }

  # Set Windows Update to manual (managed by patch management process)
  registry_value { 'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\NoAutoUpdate':
    ensure => present,
    type   => dword,
    data   => 1,
  }

  # Configure Windows Error Reporting to disabled
  registry_value { 'HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting\Disabled':
    ensure => present,
    type   => dword,
    data   => 1,
  }

  # Set hostname from EC2 tags if available
  if $facts['ec2_metadata'] and $facts['ec2_metadata']['tags'] and $facts['ec2_metadata']['tags']['Name'] {
    $hostname = $facts['ec2_metadata']['tags']['Name']

    exec { 'set-computer-name':
      command => "Rename-Computer -NewName '${hostname}' -Force -ErrorAction SilentlyContinue",
      unless  => "\$env:COMPUTERNAME -eq '${hostname}'",
      path    => ['C:\Windows\System32\WindowsPowerShell\v1.0'],
      provider => powershell,
    }
  }
}
