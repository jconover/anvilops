# @summary SQL Server configuration profile for Windows
#
# This profile manages SQL Server post-installation configuration including
# data/log/backup directory setup, memory settings, service configuration,
# and firewall rules. It does NOT install SQL Server itself - that's done
# via the AMI or separate installation process.
#
# @param data_drive
#   Drive letter for SQL Server data files
# @param log_drive
#   Drive letter for SQL Server transaction log files
# @param backup_drive
#   Drive letter for SQL Server backup files
# @param port
#   TCP port for SQL Server instance
# @param instance_name
#   SQL Server instance name (use MSSQLSERVER for default instance)
# @param max_memory_mb
#   Maximum memory for SQL Server in MB (leave undef for auto-calculation)
# @param enable_sql_agent
#   Whether to ensure SQL Server Agent is running
#
# @example Basic usage
#   include profile::sql_server
#
# @example With custom drives and port
#   class { 'profile::sql_server':
#     data_drive   => 'E:',
#     log_drive    => 'L:',
#     backup_drive => 'B:',
#     port         => 1434,
#   }
#
class profile::sql_server (
  String $data_drive   = 'D:',
  String $log_drive    = 'E:',
  String $backup_drive = 'F:',
  Integer[1024, 65535] $port = 1433,
  String $instance_name = 'MSSQLSERVER',
  Optional[Integer] $max_memory_mb = undef,
  Boolean $enable_sql_agent = true,
) {
  # Fail fast if not Windows
  if $facts['os']['family'] != 'windows' {
    fail("profile::sql_server can only be applied to Windows systems, not ${facts['os']['family']}")
  }

  # Create SQL Server directory structure
  $data_path = "${data_drive}\\SQLData"
  $log_path = "${log_drive}\\SQLLogs"
  $backup_path = "${backup_drive}\\SQLBackups"
  $tempdb_path = "${data_drive}\\SQLTempDB"

  # Ensure drives exist before creating directories
  file { $data_path:
    ensure => directory,
  }

  file { $log_path:
    ensure => directory,
  }

  file { $backup_path:
    ensure => directory,
  }

  file { $tempdb_path:
    ensure => directory,
  }

  # Set permissions on SQL directories (grant SQL Server service account access)
  # Note: This requires the SQL Server service account name - typically NT Service\MSSQLSERVER
  $sql_service_account = "NT Service\\${instance_name}"

  exec { 'set-sqldata-permissions':
    command  => "icacls.exe '${data_path}' /grant '${sql_service_account}:(OI)(CI)F' /T",
    unless   => "icacls.exe '${data_path}' | Select-String '${sql_service_account}.*F' -Quiet",
    path     => ['C:\Windows\System32'],
    require  => File[$data_path],
  }

  exec { 'set-sqllogs-permissions':
    command  => "icacls.exe '${log_path}' /grant '${sql_service_account}:(OI)(CI)F' /T",
    unless   => "icacls.exe '${log_path}' | Select-String '${sql_service_account}.*F' -Quiet",
    path     => ['C:\Windows\System32'],
    require  => File[$log_path],
  }

  exec { 'set-sqlbackups-permissions':
    command  => "icacls.exe '${backup_path}' /grant '${sql_service_account}:(OI)(CI)F' /T",
    unless   => "icacls.exe '${backup_path}' | Select-String '${sql_service_account}.*F' -Quiet",
    path     => ['C:\Windows\System32'],
    require  => File[$backup_path],
  }

  exec { 'set-sqltempdb-permissions':
    command  => "icacls.exe '${tempdb_path}' /grant '${sql_service_account}:(OI)(CI)F' /T",
    unless   => "icacls.exe '${tempdb_path}' | Select-String '${sql_service_account}.*F' -Quiet",
    path     => ['C:\Windows\System32'],
    require  => File[$tempdb_path],
  }

  # Ensure SQL Server service is running
  service { $instance_name:
    ensure => running,
    enable => true,
  }

  # Ensure SQL Server Agent is running (if enabled)
  if $enable_sql_agent {
    $agent_service = $instance_name ? {
      'MSSQLSERVER' => 'SQLSERVERAGENT',
      default       => "SQLAgent\$${instance_name}",
    }

    service { $agent_service:
      ensure  => running,
      enable  => true,
      require => Service[$instance_name],
    }
  }

  # Calculate max memory if not specified (total memory - 4GB for OS)
  if $max_memory_mb {
    $calculated_max_memory = $max_memory_mb
  } else {
    # Get total physical memory in MB and reserve 4GB for OS
    $total_memory_mb = $facts['memory']['system']['total_bytes'] / 1024 / 1024
    $calculated_max_memory = Integer($total_memory_mb - 4096)
  }

  # Configure SQL Server max memory setting
  exec { 'configure-sql-max-memory':
    command  => @("EOC"/L),
      sqlcmd.exe -S localhost -Q "EXEC sys.sp_configure N'show advanced options', N'1'; RECONFIGURE WITH OVERRIDE; EXEC sys.sp_configure N'max server memory (MB)', N'${calculated_max_memory}'; RECONFIGURE WITH OVERRIDE;"
      | EOC
    unless   => @("EOC"/L),
      \$result = sqlcmd.exe -S localhost -Q "EXEC sys.sp_configure N'max server memory (MB)'" -h -1 -W
      \$currentValue = (\$result | Select-String -Pattern '^\\s*\\d+\\s+(\\d+)').Matches.Groups[1].Value
      if (\$currentValue -eq '${calculated_max_memory}') { exit 0 } else { exit 1 }
      | EOC
    path     => ['C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn', 'C:\Program Files\Microsoft SQL Server\160\Tools\Binn', 'C:\Windows\System32'],
    provider => powershell,
    require  => Service[$instance_name],
  }

  # Configure SQL Server to use static TCP port
  exec { 'configure-sql-tcp-port':
    command  => @("EOC"/L),
      \$smo = [System.Reflection.Assembly]::LoadWithPartialName('Microsoft.SqlServer.SqlWmiManagement')
      \$wmi = New-Object Microsoft.SqlServer.Management.Smo.Wmi.ManagedComputer
      \$instance = \$wmi.ServerInstances | Where-Object { \$_.Name -eq '${instance_name}' }
      \$tcp = \$instance.ServerProtocols | Where-Object { \$_.Name -eq 'Tcp' }
      \$ipAll = \$tcp.IPAddresses | Where-Object { \$_.Name -eq 'IPAll' }
      \$ipAll.IPAddressProperties['TcpPort'].Value = '${port}'
      \$ipAll.IPAddressProperties['TcpDynamicPorts'].Value = ''
      \$tcp.Alter()
      Restart-Service -Name '${instance_name}' -Force
      | EOC
    unless   => @("EOC"/L),
      \$smo = [System.Reflection.Assembly]::LoadWithPartialName('Microsoft.SqlServer.SqlWmiManagement')
      \$wmi = New-Object Microsoft.SqlServer.Management.Smo.Wmi.ManagedComputer
      \$instance = \$wmi.ServerInstances | Where-Object { \$_.Name -eq '${instance_name}' }
      \$tcp = \$instance.ServerProtocols | Where-Object { \$_.Name -eq 'Tcp' }
      \$ipAll = \$tcp.IPAddresses | Where-Object { \$_.Name -eq 'IPAll' }
      if (\$ipAll.IPAddressProperties['TcpPort'].Value -eq '${port}') { exit 0 } else { exit 1 }
      | EOC
    provider => powershell,
    require  => Service[$instance_name],
  }

  # Open firewall port for SQL Server
  exec { "firewall-allow-sql-${port}":
    command => "netsh.exe advfirewall firewall add rule name=\"SQL Server Port ${port}\" dir=in action=allow protocol=TCP localport=${port}",
    unless  => "netsh.exe advfirewall firewall show rule name=\"SQL Server Port ${port}\" | Select-String \"SQL Server Port ${port}\" -Quiet",
    path    => ['C:\Windows\System32'],
  }

  # Configure SQL Server instant file initialization (performance optimization)
  exec { 'enable-instant-file-initialization':
    command  => @("EOC"/L),
      \$account = '${sql_service_account}'
      \$right = 'SeManageVolumePrivilege'
      \$tempFile = [System.IO.Path]::GetTempFileName()
      secedit.exe /export /cfg \$tempFile /quiet
      \$content = Get-Content \$tempFile
      \$found = \$false
      \$newContent = \$content | ForEach-Object {
        if (\$_ -match "^\$right\\s*=") {
          \$found = \$true
          if (\$_ -notmatch [regex]::Escape(\$account)) {
            \$_ + ",\$account"
          } else {
            \$_
          }
        } else {
          \$_
        }
      }
      if (-not \$found) {
        \$newContent += "\$right = \$account"
      }
      \$newContent | Set-Content \$tempFile
      secedit.exe /configure /db secedit.sdb /cfg \$tempFile /areas USER_RIGHTS /quiet
      Remove-Item \$tempFile -Force
      gpupdate.exe /force
      | EOC
    unless   => @("EOC"/L),
      \$account = '${sql_service_account}'
      \$right = 'SeManageVolumePrivilege'
      \$tempFile = [System.IO.Path]::GetTempFileName()
      secedit.exe /export /cfg \$tempFile /quiet
      \$content = Get-Content \$tempFile
      \$hasRight = \$content | Where-Object { \$_ -match "^\$right\\s*=" -and \$_ -match [regex]::Escape(\$account) }
      Remove-Item \$tempFile -Force
      if (\$hasRight) { exit 0 } else { exit 1 }
      | EOC
    provider => powershell,
  }

  # Configure SQL Server error log retention (keep 30 logs)
  exec { 'configure-errorlog-retention':
    command  => @(EOC/L),
      sqlcmd.exe -S localhost -Q "EXEC sys.xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'NumErrorLogs', REG_DWORD, 30"
      | EOC
    unless   => @(EOC/L),
      $result = sqlcmd.exe -S localhost -Q "EXEC sys.xp_instance_regread N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'NumErrorLogs'" -h -1 -W
      $currentValue = ($result | Select-String -Pattern '^\s*NumErrorLogs\s+REG_DWORD\s+(\d+)').Matches.Groups[1].Value
      if ($currentValue -eq '30') { exit 0 } else { exit 1 }
      | EOC
    path     => ['C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn', 'C:\Program Files\Microsoft SQL Server\160\Tools\Binn', 'C:\Windows\System32'],
    provider => powershell,
    require  => Service[$instance_name],
  }
}
