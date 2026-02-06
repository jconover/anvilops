# @summary .NET runtime and SDK profile for Windows
#
# This profile installs the .NET runtime and SDK on Windows systems using
# Chocolatey package manager. It supports installing multiple versions side-by-side
# and ensures IIS integration if IIS is present on the system.
#
# @param version
#   .NET version to install (e.g., '6.0', '7.0', '8.0')
# @param install_sdk
#   Whether to install the full SDK (true) or just the runtime (false)
# @param install_aspnet
#   Whether to install the ASP.NET Core runtime
# @param ensure_iis_integration
#   Whether to ensure IIS hosting bundle is installed (only if IIS present)
#
# @example Basic usage (installs latest LTS)
#   include profile::dotnet
#
# @example Install specific version with SDK
#   class { 'profile::dotnet':
#     version     => '8.0',
#     install_sdk => true,
#   }
#
class profile::dotnet (
  String $version = '8.0',
  Boolean $install_sdk = true,
  Boolean $install_aspnet = true,
  Boolean $ensure_iis_integration = true,
) {
  # Fail fast if not Windows
  if $facts['os']['family'] != 'windows' {
    fail("profile::dotnet can only be applied to Windows systems, not ${facts['os']['family']}")
  }

  # Ensure Chocolatey is installed (should be from profile::windows_base)
  require chocolatey

  # Determine package names based on version
  if $install_sdk {
    # Install full SDK (includes runtime)
    package { "dotnet-sdk-${version}":
      ensure   => installed,
      provider => chocolatey,
    }

    $runtime_require = Package["dotnet-sdk-${version}"]
  } else {
    # Install just the runtime
    package { "dotnet-${version}-runtime":
      ensure   => installed,
      provider => chocolatey,
    }

    $runtime_require = Package["dotnet-${version}-runtime"]
  }

  # Install ASP.NET Core runtime if requested
  if $install_aspnet {
    package { "dotnet-${version}-aspnetruntime":
      ensure   => installed,
      provider => chocolatey,
      require  => $runtime_require,
    }

    $aspnet_require = Package["dotnet-${version}-aspnetruntime"]
  } else {
    $aspnet_require = $runtime_require
  }

  # Check if IIS is installed
  $iis_installed = $facts['iis_installed'] ? {
    true    => true,
    default => false,
  }

  # If IIS is present and integration is requested, install hosting bundle
  if $ensure_iis_integration and $iis_installed {
    package { "dotnet-${version}-windowshosting":
      ensure   => installed,
      provider => chocolatey,
      require  => $aspnet_require,
    }

    # Restart IIS after hosting bundle installation
    exec { 'restart-iis-after-dotnet':
      command     => 'iisreset.exe /restart',
      refreshonly => true,
      subscribe   => Package["dotnet-${version}-windowshosting"],
      path        => ['C:\Windows\System32'],
    }

    # Ensure ASP.NET Core Module is registered
    exec { 'verify-aspnetcore-module':
      command  => @(EOC/L),
        Import-Module WebAdministration
        $module = Get-WebGlobalModule -Name AspNetCoreModuleV2 -ErrorAction SilentlyContinue
        if ($null -eq $module) {
          Write-Error "ASP.NET Core Module V2 not found"
          exit 1
        }
        | EOC
      provider => powershell,
      require  => [Package["dotnet-${version}-windowshosting"], Exec['restart-iis-after-dotnet']],
    }
  }

  # Set DOTNET environment variables
  $dotnet_root = 'C:\Program Files\dotnet'

  registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment\DOTNET_ROOT':
    ensure => present,
    type   => string,
    data   => $dotnet_root,
  }

  # Add dotnet to system PATH if not already present
  exec { 'add-dotnet-to-path':
    command  => @("EOC"/L),
      \$currentPath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
      if (\$currentPath -notlike '*${dotnet_root}*') {
        \$newPath = "\${currentPath};${dotnet_root}"
        [Environment]::SetEnvironmentVariable('Path', \$newPath, 'Machine')
      }
      | EOC
    unless   => "\$env:Path -like '*${dotnet_root}*'",
    provider => powershell,
    require  => $runtime_require,
  }

  # Verify .NET installation
  exec { 'verify-dotnet-installation':
    command  => "dotnet.exe --list-sdks | Select-String -Pattern '${version}' -Quiet",
    provider => powershell,
    require  => $runtime_require,
  }

  # Configure .NET telemetry opt-out (privacy)
  registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment\DOTNET_CLI_TELEMETRY_OPTOUT':
    ensure => present,
    type   => string,
    data   => '1',
  }

  # Enable .NET Server GC for better server performance
  registry_value { 'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment\COMPlus_gcServer':
    ensure => present,
    type   => string,
    data   => '1',
  }

  # Configure .NET to use TLS 1.2+ by default
  registry_value { 'HKLM\SOFTWARE\Microsoft\.NETFramework\v4.0.30319\SchUseStrongCrypto':
    ensure => present,
    type   => dword,
    data   => 1,
  }

  registry_value { 'HKLM\SOFTWARE\Wow6432Node\Microsoft\.NETFramework\v4.0.30319\SchUseStrongCrypto':
    ensure => present,
    type   => dword,
    data   => 1,
  }
}
