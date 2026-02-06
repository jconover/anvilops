# @summary Developer tools profile for Windows workstations
#
# This profile installs common developer tools on Windows systems using
# Chocolatey. It's designed for development workstations and includes
# IDEs, version control, containers, and language runtimes.
#
# @param packages
#   Array of Chocolatey package names to install
# @param configure_git
#   Whether to configure Git with sensible defaults
# @param git_user_name
#   Git global user.name setting (leave empty to skip)
# @param git_user_email
#   Git global user.email setting (leave empty to skip)
# @param enable_wsl
#   Whether to enable Windows Subsystem for Linux
#
# @example Basic usage
#   include profile::dev_tools
#
# @example With custom packages
#   class { 'profile::dev_tools':
#     packages => ['vscode', 'git', 'python3', 'golang'],
#   }
#
class profile::dev_tools (
  Array[String] $packages = [
    'vscode',
    'git',
    'docker-desktop',
    'nodejs-lts',
    'python3',
    'powershell-core',
    '7zip',
    'notepadplusplus',
    'postman',
  ],
  Boolean $configure_git = true,
  String $git_user_name = '',
  String $git_user_email = '',
  Boolean $enable_wsl = false,
) {
  # Fail fast if not Windows
  if $facts['os']['family'] != 'windows' {
    fail("profile::dev_tools can only be applied to Windows systems, not ${facts['os']['family']}")
  }

  # Ensure Chocolatey is installed (should be from profile::windows_base)
  require chocolatey

  # Install all requested packages
  $packages.each |String $package| {
    package { $package:
      ensure   => installed,
      provider => chocolatey,
    }
  }

  # Configure Git if requested
  if $configure_git and 'git' in $packages {
    # Set global Git configuration
    if $git_user_name != '' {
      exec { 'git-config-username':
        command  => "git.exe config --global user.name '${git_user_name}'",
        unless   => "git.exe config --global user.name | Select-String -Pattern '${git_user_name}' -Quiet",
        path     => ['C:\Program Files\Git\cmd'],
        require  => Package['git'],
      }
    }

    if $git_user_email != '' {
      exec { 'git-config-useremail':
        command  => "git.exe config --global user.email '${git_user_email}'",
        unless   => "git.exe config --global user.email | Select-String -Pattern '${git_user_email}' -Quiet",
        path     => ['C:\Program Files\Git\cmd'],
        require  => Package['git'],
      }
    }

    # Set sensible Git defaults
    exec { 'git-config-autocrlf':
      command  => 'git.exe config --global core.autocrlf true',
      unless   => 'git.exe config --global core.autocrlf | Select-String -Pattern "true" -Quiet',
      path     => ['C:\Program Files\Git\cmd'],
      require  => Package['git'],
    }

    exec { 'git-config-defaultbranch':
      command  => 'git.exe config --global init.defaultBranch main',
      unless   => 'git.exe config --global init.defaultBranch | Select-String -Pattern "main" -Quiet',
      path     => ['C:\Program Files\Git\cmd'],
      require  => Package['git'],
    }

    exec { 'git-config-credential-helper':
      command  => 'git.exe config --global credential.helper manager',
      unless   => 'git.exe config --global credential.helper | Select-String -Pattern "manager" -Quiet',
      path     => ['C:\Program Files\Git\cmd'],
      require  => Package['git'],
    }

    # Enable long paths for Git (Windows limitation workaround)
    exec { 'git-config-longpaths':
      command  => 'git.exe config --global core.longpaths true',
      unless   => 'git.exe config --global core.longpaths | Select-String -Pattern "true" -Quiet',
      path     => ['C:\Program Files\Git\cmd'],
      require  => Package['git'],
    }
  }

  # Configure Docker Desktop if installed
  if 'docker-desktop' in $packages {
    # Ensure Docker Desktop service is set to start automatically
    service { 'com.docker.service':
      ensure  => running,
      enable  => true,
      require => Package['docker-desktop'],
    }

    # Note: Docker Desktop settings are per-user and managed via GUI/JSON config
    # For enterprise settings, consider using Docker Desktop Business with registry policy
  }

  # Enable WSL if requested
  if $enable_wsl {
    # Enable WSL feature
    windowsfeature { 'Microsoft-Windows-Subsystem-Linux':
      ensure => present,
    }

    # Enable Virtual Machine Platform (required for WSL 2)
    windowsfeature { 'VirtualMachinePlatform':
      ensure => present,
    }

    # Set WSL 2 as default
    exec { 'set-wsl-default-version':
      command  => 'wsl.exe --set-default-version 2',
      unless   => 'wsl.exe --status | Select-String -Pattern "Default Version: 2" -Quiet',
      path     => ['C:\Windows\System32'],
      require  => [Windowsfeature['Microsoft-Windows-Subsystem-Linux'], Windowsfeature['VirtualMachinePlatform']],
    }

    # Note: Actual WSL distro installation should be done per-user
    # wsl --install -d Ubuntu
  }

  # Configure VS Code if installed (system-wide settings)
  if 'vscode' in $packages {
    # Install useful VS Code extensions via CLI
    $vscode_extensions = [
      'ms-vscode.powershell',
      'ms-python.python',
      'ms-azuretools.vscode-docker',
      'eamodio.gitlens',
      'esbenp.prettier-vscode',
    ]

    $vscode_extensions.each |String $extension| {
      exec { "install-vscode-extension-${extension}":
        command  => "code.cmd --install-extension ${extension} --force",
        unless   => "code.cmd --list-extensions | Select-String -Pattern '${extension}' -Quiet",
        path     => ['C:\Program Files\Microsoft VS Code\bin', 'C:\Users\anvilops-svc\AppData\Local\Programs\Microsoft VS Code\bin'],
        require  => Package['vscode'],
        timeout  => 300,
      }
    }
  }

  # Configure Python if installed
  if 'python3' in $packages {
    # Add Python to system PATH (should be done by Chocolatey, but verify)
    exec { 'verify-python-in-path':
      command  => 'python.exe --version',
      path     => ['C:\Python312', 'C:\Python311', 'C:\Python310', 'C:\Windows\System32'],
      require  => Package['python3'],
    }

    # Upgrade pip
    exec { 'upgrade-pip':
      command  => 'python.exe -m pip install --upgrade pip',
      path     => ['C:\Python312', 'C:\Python311', 'C:\Python310', 'C:\Windows\System32'],
      require  => Package['python3'],
    }

    # Install common Python packages
    $python_packages = [
      'virtualenv',
      'pipenv',
      'requests',
      'boto3',
    ]

    $python_packages.each |String $pypackage| {
      exec { "install-python-package-${pypackage}":
        command  => "python.exe -m pip install ${pypackage}",
        unless   => "python.exe -m pip list | Select-String -Pattern '${pypackage}' -Quiet",
        path     => ['C:\Python312', 'C:\Python311', 'C:\Python310', 'C:\Windows\System32'],
        require  => Exec['upgrade-pip'],
        timeout  => 300,
      }
    }
  }

  # Configure Node.js if installed
  if 'nodejs-lts' in $packages {
    # Set npm global prefix to avoid permission issues
    exec { 'npm-config-prefix':
      command  => 'npm.cmd config set prefix "C:\npm-global"',
      unless   => 'npm.cmd config get prefix | Select-String -Pattern "C:\\\\npm-global" -Quiet',
      path     => ['C:\Program Files\nodejs'],
      require  => Package['nodejs-lts'],
    }

    # Add npm global to PATH
    exec { 'add-npm-global-to-path':
      command  => @(EOC/L),
        $currentPath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        if ($currentPath -notlike '*C:\npm-global*') {
          $newPath = "${currentPath};C:\npm-global"
          [Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine')
        }
        | EOC
      unless   => '$env:Path -like "*C:\npm-global*"',
      provider => powershell,
      require  => Package['nodejs-lts'],
    }
  }
}
