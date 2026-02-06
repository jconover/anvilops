# @summary IIS web server profile for Windows
#
# This profile installs and configures Internet Information Services (IIS) with
# best practices for production use. It manages Windows features, application pools,
# and firewall rules.
#
# @param features
#   Array of IIS Windows features to install
# @param remove_default_site
#   Whether to remove the default IIS website
# @param app_pool_name
#   Name of the default application pool to create
# @param app_pool_runtime_version
#   .NET CLR version for the application pool
# @param app_pool_pipeline_mode
#   Managed pipeline mode (Integrated or Classic)
#
# @example Basic usage
#   include profile::iis
#
# @example With custom app pool settings
#   class { 'profile::iis':
#     app_pool_name            => 'MyApp',
#     app_pool_runtime_version => 'v4.0',
#   }
#
class profile::iis (
  Array[String] $features = [
    'Web-Server',
    'Web-WebServer',
    'Web-Common-Http',
    'Web-Default-Doc',
    'Web-Dir-Browsing',
    'Web-Http-Errors',
    'Web-Static-Content',
    'Web-Http-Redirect',
    'Web-Health',
    'Web-Http-Logging',
    'Web-Performance',
    'Web-Stat-Compression',
    'Web-Security',
    'Web-Filtering',
    'Web-App-Dev',
    'Web-Net-Ext45',
    'Web-Asp-Net45',
    'Web-ISAPI-Ext',
    'Web-ISAPI-Filter',
    'Web-Mgmt-Tools',
    'Web-Mgmt-Console',
  ],
  Boolean $remove_default_site = true,
  String $app_pool_name = 'AnvilOps',
  String $app_pool_runtime_version = 'v4.0',
  Enum['Integrated', 'Classic'] $app_pool_pipeline_mode = 'Integrated',
) {
  # Fail fast if not Windows
  if $facts['os']['family'] != 'windows' {
    fail("profile::iis can only be applied to Windows systems, not ${facts['os']['family']}")
  }

  # Install IIS features
  $features.each |String $feature| {
    windowsfeature { $feature:
      ensure => present,
    }
  }

  # Wait for IIS installation to complete before managing sites
  exec { 'wait-for-iis':
    command  => 'Start-Sleep -Seconds 5',
    provider => powershell,
    require  => Windowsfeature['Web-Server'],
    before   => Exec['import-webadministration'],
  }

  # Import WebAdministration module
  exec { 'import-webadministration':
    command  => 'Import-Module WebAdministration',
    unless   => 'Get-Module -ListAvailable -Name WebAdministration',
    provider => powershell,
  }

  # Remove default website if configured
  if $remove_default_site {
    exec { 'remove-default-website':
      command  => 'Remove-Website -Name "Default Web Site" -ErrorAction SilentlyContinue',
      onlyif   => 'Get-Website -Name "Default Web Site" -ErrorAction SilentlyContinue',
      provider => powershell,
      require  => Exec['import-webadministration'],
    }
  }

  # Create custom application pool
  exec { "create-apppool-${app_pool_name}":
    command  => @("EOC"/L),
      Import-Module WebAdministration
      New-WebAppPool -Name '${app_pool_name}' -Force
      Set-ItemProperty IIS:\\AppPools\\${app_pool_name} -Name managedRuntimeVersion -Value '${app_pool_runtime_version}'
      Set-ItemProperty IIS:\\AppPools\\${app_pool_name} -Name managedPipelineMode -Value '${app_pool_pipeline_mode}'
      Set-ItemProperty IIS:\\AppPools\\${app_pool_name} -Name processModel.identityType -Value 'ApplicationPoolIdentity'
      Set-ItemProperty IIS:\\AppPools\\${app_pool_name} -Name startMode -Value 'AlwaysRunning'
      Set-ItemProperty IIS:\\AppPools\\${app_pool_name} -Name recycling.periodicRestart.time -Value '00:00:00'
      | EOC
    unless   => "\$null -ne (Get-WebAppPoolState -Name '${app_pool_name}' -ErrorAction SilentlyContinue)",
    provider => powershell,
    require  => Exec['import-webadministration'],
  }

  # Ensure application pool is started
  exec { "start-apppool-${app_pool_name}":
    command  => "Start-WebAppPool -Name '${app_pool_name}'",
    unless   => "(Get-WebAppPoolState -Name '${app_pool_name}').Value -eq 'Started'",
    provider => powershell,
    require  => Exec["create-apppool-${app_pool_name}"],
  }

  # Configure IIS logging
  exec { 'configure-iis-logging':
    command  => @(EOC/L),
      Import-Module WebAdministration
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.applicationHost/sites/siteDefaults/logFile' -Name 'logFormat' -Value 'W3C'
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.applicationHost/sites/siteDefaults/logFile' -Name 'directory' -Value 'C:\inetpub\logs\LogFiles'
      | EOC
    provider => powershell,
    require  => Exec['import-webadministration'],
  }

  # Ensure W3SVC (IIS) service is running
  service { 'W3SVC':
    ensure  => running,
    enable  => true,
    require => Windowsfeature['Web-Server'],
  }

  # Ensure WAS (Windows Process Activation Service) is running
  service { 'WAS':
    ensure  => running,
    enable  => true,
    require => Windowsfeature['Web-Server'],
  }

  # Open firewall ports for HTTP and HTTPS
  exec { 'firewall-allow-http':
    command => 'netsh.exe advfirewall firewall add rule name="IIS HTTP" dir=in action=allow protocol=TCP localport=80',
    unless  => 'netsh.exe advfirewall firewall show rule name="IIS HTTP" | Select-String "IIS HTTP" -Quiet',
    path    => ['C:\Windows\System32'],
  }

  exec { 'firewall-allow-https':
    command => 'netsh.exe advfirewall firewall add rule name="IIS HTTPS" dir=in action=allow protocol=TCP localport=443',
    unless  => 'netsh.exe advfirewall firewall show rule name="IIS HTTPS" | Select-String "IIS HTTPS" -Quiet',
    path    => ['C:\Windows\System32'],
  }

  # Disable IIS default authentication methods, enable Windows Auth
  exec { 'configure-iis-auth':
    command  => @(EOC/L),
      Import-Module WebAdministration
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/security/authentication/anonymousAuthentication' -Name 'enabled' -Value 'True'
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/security/authentication/basicAuthentication' -Name 'enabled' -Value 'False'
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/security/authentication/windowsAuthentication' -Name 'enabled' -Value 'True'
      | EOC
    provider => powershell,
    require  => Exec['import-webadministration'],
  }

  # Configure request filtering (security)
  exec { 'configure-request-filtering':
    command  => @(EOC/L),
      Import-Module WebAdministration
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/security/requestFiltering/requestLimits' -Name 'maxAllowedContentLength' -Value 30000000
      Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/security/requestFiltering/requestLimits' -Name 'maxQueryString' -Value 2048
      | EOC
    provider => powershell,
    require  => Exec['import-webadministration'],
  }
}
