# AnvilOps Profile Module

This module contains service-oriented profile classes for the AnvilOps platform. These profiles implement the "Profile" layer of the Roles & Profiles pattern, providing reusable configurations for cross-cutting concerns like monitoring, patching, firewall, and security.

## Profiles

### `profile::monitoring`

Manages CloudWatch agent for comprehensive system monitoring on both Linux and Windows.

**Features:**
- Installs and configures Amazon CloudWatch agent
- Collects CPU, memory, disk, network metrics
- Ships system logs to CloudWatch Logs
- Cross-platform support (RHEL, Amazon Linux, Ubuntu, Debian, Windows)

**Parameters:**
- `agent_version` - CloudWatch agent version (default: 'latest')
- `log_group_prefix` - CloudWatch Logs group prefix (default: '/anvilops')
- `metrics_collection_interval` - Metrics collection interval in seconds (default: 60)
- `log_retention_days` - Log retention period (default: 30)

**Example:**
```puppet
class { 'profile::monitoring':
  metrics_collection_interval => 300,
  log_retention_days          => 90,
}
```

---

### `profile::patching`

Configures automated OS patching policies for security updates.

**Features:**
- Linux: Manages yum-cron/dnf-automatic (RHEL) or unattended-upgrades (Debian/Ubuntu)
- Windows: Configures Windows Update via registry
- Configurable patch windows and auto-reboot behavior
- Security-first patching (CriticalUpdates + SecurityUpdates by default)

**Parameters:**
- `patch_window` - Patch installation time (default: 'Sunday 02:00')
- `auto_reboot` - Auto-reboot after patching (default: false)
- `patch_categories_windows` - Windows update categories (default: ['SecurityUpdates', 'CriticalUpdates'])
- `auto_update_security_linux` - Auto-install security updates on Linux (default: true)

**Example:**
```puppet
class { 'profile::patching':
  patch_window => 'Saturday 03:00',
  auto_reboot  => true,
}
```

---

### `profile::firewall`

Manages host-based firewall rules for network security.

**Features:**
- Linux: Manages firewalld with service and port rules
- Windows: Manages Windows Firewall profiles and rules
- Default-deny policy option
- Automatic VPC CIDR whitelisting for ICMP
- RDP and WinRM allowed by default on Windows

**Parameters:**
- `allowed_services_linux` - Firewalld services to allow (default: ['ssh'])
- `allowed_ports` - Hash of ports to allow (format: { 'port/protocol' => 'description' })
- `default_deny` - Set default policy to deny/drop (default: true)
- `windows_firewall_profiles` - Windows Firewall profile states (default: all enabled)
- `vpc_cidr` - VPC CIDR for internal communication (default: '10.0.0.0/8')

**Example:**
```puppet
class { 'profile::firewall':
  allowed_services_linux => ['ssh', 'http', 'https'],
  allowed_ports          => {
    '8080/tcp' => 'Application port',
    '9090/tcp' => 'Metrics port',
  },
}
```

---

### `profile::security`

CIS/STIG-inspired security baseline enforcement.

**Features:**
- Linux: Hardened SSH configuration, auditd logging, filesystem restrictions
- Windows: Password policy, SMBv1 disabled, LLMNR/NetBIOS disabled, audit logging
- USB storage blocking option
- Comprehensive audit logging for compliance
- Cross-platform security hardening

**Parameters:**

**Linux SSH:**
- `ssh_permit_root_login` - Allow root login via SSH (default: false)
- `ssh_password_auth` - Allow password authentication (default: false)
- `ssh_max_auth_tries` - Max authentication attempts (default: 3)

**Windows Password Policy:**
- `password_min_length` - Minimum password length (default: 14)
- `password_max_age_days` - Maximum password age (default: 90)
- `account_lockout_threshold` - Failed login attempts before lockout (default: 5)
- `account_lockout_duration` - Lockout duration in minutes (default: 30)

**General:**
- `disable_usb_storage` - Disable USB storage devices (default: false)
- `enable_audit_logging` - Enable comprehensive audit logging (default: true)

**Example:**
```puppet
class { 'profile::security':
  ssh_permit_root_login      => false,
  ssh_password_auth          => false,
  password_min_length        => 16,
  account_lockout_threshold  => 3,
  enable_audit_logging       => true,
}
```

---

## Usage in Roles

These profiles are designed to be included in role classes:

```puppet
class role::web_server {
  include profile::base
  include profile::monitoring
  include profile::patching
  include profile::firewall
  include profile::security
  include profile::web
}
```

## Cross-Platform Support

All profiles use OS detection via `$facts['os']['family']` to provide appropriate configuration for:

- **Linux**: RedHat (RHEL, CentOS, Amazon Linux), Debian (Ubuntu, Debian)
- **Windows**: Windows Server 2016, 2019, 2022

## Templates

All configuration files are managed via EPP templates:

- `cloudwatch_config_linux.epp` - CloudWatch agent config for Linux
- `cloudwatch_config_windows.epp` - CloudWatch agent config for Windows
- `sshd_config.epp` - Hardened SSH configuration
- `yum_cron.epp` - yum-cron/dnf-automatic configuration
- `unattended_upgrades.epp` - Debian/Ubuntu unattended-upgrades config

## Dependencies

These profiles assume the following are available:

- **Linux**: Package repositories configured (EPEL for RHEL/CentOS if needed)
- **Windows**: Chocolatey package provider configured
- **All**: AWS IAM instance role with CloudWatch permissions

## Puppet Agent Configuration

These profiles are enforced every 30 minutes by the Puppet agent running on each server. Changes are automatically corrected to maintain compliance with the defined baseline.

## License

Apache-2.0

## Author

AnvilOps Platform Engineering Team
