# frozen_string_literal: true

# Custom Facter fact: anvilops_compliance
#
# Reports per-check compliance status for AnvilOps-managed servers.
# Results are exposed in PuppetDB and visible on PE Console node pages,
# enabling compliance dashboards, PQL queries for non-compliant nodes,
# and automated evidence collection for auditors.
#
# Each check maps to a specific CIS Benchmark or STIG control ID.
# The fact produces a structured hash:
#   {
#     "ssh_root_login_disabled"     => true,
#     "ssh_password_auth_disabled"  => true,
#     "shadow_permissions_secure"   => true,
#     ...
#     "checks_passed"  => 12,
#     "checks_total"   => 14,
#     "score"          => "12/14",
#     "score_percent"  => 85,
#     "compliant"      => false
#   }
#
# Design decisions:
# - Every check is wrapped in begin/rescue to prevent fact resolution failure
# - Checks are lightweight: read files, check permissions, query systemctl
# - No network calls, no package manager queries, no heavy computation
# - Windows checks use netsh/reg query (fast, no WMI overhead where possible)

Facter.add(:anvilops_compliance) do
  confine kernel: ['Linux', 'windows']

  setcode do
    results = {}

    os_family = Facter.value(:os)['family'] rescue nil

    case os_family
    when 'RedHat', 'Debian'
      # ================================================================
      # Linux Compliance Checks
      # ================================================================

      # CIS 5.2.8 -- SSH root login disabled
      begin
        if File.exist?('/etc/ssh/sshd_config')
          sshd_lines = File.readlines('/etc/ssh/sshd_config')
          # Check for effective PermitRootLogin setting (last uncommented wins)
          root_login_lines = sshd_lines.select { |l| l.strip =~ /^PermitRootLogin\s+/i }
          if root_login_lines.any?
            last_setting = root_login_lines.last.strip.split(/\s+/)[1].downcase
            results['ssh_root_login_disabled'] = (last_setting == 'no')
          else
            # Default in modern OpenSSH is prohibit-password, which counts as disabled
            results['ssh_root_login_disabled'] = true
          end
        else
          results['ssh_root_login_disabled'] = false
        end
      rescue StandardError
        results['ssh_root_login_disabled'] = false
      end

      # CIS 5.2.4 -- SSH password authentication disabled
      begin
        if File.exist?('/etc/ssh/sshd_config')
          sshd_lines = File.readlines('/etc/ssh/sshd_config')
          pwd_auth_lines = sshd_lines.select { |l| l.strip =~ /^PasswordAuthentication\s+/i }
          if pwd_auth_lines.any?
            last_setting = pwd_auth_lines.last.strip.split(/\s+/)[1].downcase
            results['ssh_password_auth_disabled'] = (last_setting == 'no')
          else
            # Default is yes, so if not explicitly set, it is NOT disabled
            results['ssh_password_auth_disabled'] = false
          end
        else
          results['ssh_password_auth_disabled'] = false
        end
      rescue StandardError
        results['ssh_password_auth_disabled'] = false
      end

      # CIS 5.2.11 -- SSH MaxAuthTries is 4 or less
      begin
        if File.exist?('/etc/ssh/sshd_config')
          sshd_lines = File.readlines('/etc/ssh/sshd_config')
          max_auth_lines = sshd_lines.select { |l| l.strip =~ /^MaxAuthTries\s+/i }
          if max_auth_lines.any?
            value = max_auth_lines.last.strip.split(/\s+/)[1].to_i
            results['ssh_max_auth_tries_compliant'] = (value <= 4)
          else
            # Default is 6, which is non-compliant
            results['ssh_max_auth_tries_compliant'] = false
          end
        else
          results['ssh_max_auth_tries_compliant'] = false
        end
      rescue StandardError
        results['ssh_max_auth_tries_compliant'] = false
      end

      # CIS 6.1.4 -- /etc/shadow permissions (should be 0000 or 0640)
      begin
        if File.exist?('/etc/shadow')
          mode = File.stat('/etc/shadow').mode & 0o7777
          results['shadow_permissions_secure'] = (mode == 0o000 || mode == 0o640)
        else
          results['shadow_permissions_secure'] = false
        end
      rescue StandardError
        results['shadow_permissions_secure'] = false
      end

      # CIS 6.1.2 -- /etc/passwd permissions (should be 0644 or more restrictive)
      begin
        if File.exist?('/etc/passwd')
          mode = File.stat('/etc/passwd').mode & 0o7777
          results['passwd_permissions_secure'] = (mode <= 0o644)
        else
          results['passwd_permissions_secure'] = false
        end
      rescue StandardError
        results['passwd_permissions_secure'] = false
      end

      # CIS 3.4 -- Firewall active (firewalld or iptables)
      begin
        firewalld_active = system('systemctl is-active --quiet firewalld 2>/dev/null')
        iptables_active = system('systemctl is-active --quiet iptables 2>/dev/null')
        results['firewall_active'] = (firewalld_active || iptables_active) ? true : false
      rescue StandardError
        results['firewall_active'] = false
      end

      # CIS 4.1.1.1 -- auditd is running
      begin
        results['auditd_running'] = system('systemctl is-active --quiet auditd 2>/dev/null') ? true : false
      rescue StandardError
        results['auditd_running'] = false
      end

      # CIS 3.1.1 -- IP forwarding disabled
      begin
        ip_forward = File.read('/proc/sys/net/ipv4/ip_forward').strip rescue nil
        results['ip_forwarding_disabled'] = (ip_forward == '0')
      rescue StandardError
        results['ip_forwarding_disabled'] = false
      end

      # CIS 3.2.2 -- ICMP redirects not accepted
      begin
        accept_redirects = File.read('/proc/sys/net/ipv4/conf/all/accept_redirects').strip rescue nil
        results['icmp_redirects_disabled'] = (accept_redirects == '0')
      rescue StandardError
        results['icmp_redirects_disabled'] = false
      end

      # CIS 3.2.7 -- Reverse path filtering enabled
      begin
        rp_filter = File.read('/proc/sys/net/ipv4/conf/all/rp_filter').strip rescue nil
        results['rp_filter_enabled'] = (rp_filter == '1')
      rescue StandardError
        results['rp_filter_enabled'] = false
      end

      # CIS 3.2.8 -- TCP SYN cookies enabled
      begin
        syncookies = File.read('/proc/sys/net/ipv4/tcp_syncookies').strip rescue nil
        results['tcp_syncookies_enabled'] = (syncookies == '1')
      rescue StandardError
        results['tcp_syncookies_enabled'] = false
      end

      # CIS 1.5.1 -- Core dumps restricted
      begin
        suid_dumpable = File.read('/proc/sys/fs/suid_dumpable').strip rescue nil
        results['core_dumps_restricted'] = (suid_dumpable == '0')
      rescue StandardError
        results['core_dumps_restricted'] = false
      end

      # CIS 1.5.3 -- ASLR enabled
      begin
        aslr = File.read('/proc/sys/kernel/randomize_va_space').strip rescue nil
        results['aslr_enabled'] = (aslr == '2')
      rescue StandardError
        results['aslr_enabled'] = false
      end

      # CIS 1.3.1 -- AIDE installed
      begin
        aide_installed = system('rpm -q aide >/dev/null 2>&1') || system('dpkg -l aide 2>/dev/null | grep -q "^ii"')
        results['aide_installed'] = aide_installed ? true : false
      rescue StandardError
        results['aide_installed'] = false
      end

      # CIS 5.3.1 -- Password quality (pwquality configured)
      begin
        if File.exist?('/etc/security/pwquality.conf')
          pwq = File.read('/etc/security/pwquality.conf')
          minlen_match = pwq.match(/^\s*minlen\s*=\s*(\d+)/)
          results['password_quality_configured'] = minlen_match && minlen_match[1].to_i >= 14
        else
          results['password_quality_configured'] = false
        end
      rescue StandardError
        results['password_quality_configured'] = false
      end

      # CIS 1.4.1 -- Bootloader permissions
      begin
        grub_paths = ['/boot/grub2/grub.cfg', '/boot/grub/grub.cfg']
        grub_file = grub_paths.find { |p| File.exist?(p) }
        if grub_file
          mode = File.stat(grub_file).mode & 0o7777
          results['bootloader_permissions_secure'] = (mode <= 0o600)
        else
          results['bootloader_permissions_secure'] = false
        end
      rescue StandardError
        results['bootloader_permissions_secure'] = false
      end

    when 'windows'
      # ================================================================
      # Windows Compliance Checks
      # ================================================================

      # CIS 9.1.1 -- Domain firewall profile enabled
      begin
        output = `netsh advfirewall show domainprofile state 2>nul`
        results['firewall_domain_enabled'] = output.to_s.include?('ON')
      rescue StandardError
        results['firewall_domain_enabled'] = false
      end

      # CIS 9.2.1 -- Private firewall profile enabled
      begin
        output = `netsh advfirewall show privateprofile state 2>nul`
        results['firewall_private_enabled'] = output.to_s.include?('ON')
      rescue StandardError
        results['firewall_private_enabled'] = false
      end

      # CIS 9.3.1 -- Public firewall profile enabled
      begin
        output = `netsh advfirewall show publicprofile state 2>nul`
        results['firewall_public_enabled'] = output.to_s.include?('ON')
      rescue StandardError
        results['firewall_public_enabled'] = false
      end

      # CIS 18.3.1 -- SMBv1 client driver disabled
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Services\\mrxsmb10" /v Start 2>nul`
        results['smb1_client_disabled'] = output.to_s.include?('0x4')
      rescue StandardError
        results['smb1_client_disabled'] = false
      end

      # CIS 18.3.2 -- SMBv1 server disabled
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters" /v SMB1 2>nul`
        results['smb1_server_disabled'] = output.to_s.include?('0x0')
      rescue StandardError
        results['smb1_server_disabled'] = false
      end

      # CIS 2.3.11.5 -- LAN Manager authentication level is NTLMv2 only
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v LmCompatibilityLevel 2>nul`
        results['ntlmv2_only'] = output.to_s.include?('0x5')
      rescue StandardError
        results['ntlmv2_only'] = false
      end

      # CIS 2.3.11.4 -- No LM hash storage
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v NoLMHash 2>nul`
        results['no_lm_hash'] = output.to_s.include?('0x1')
      rescue StandardError
        results['no_lm_hash'] = false
      end

      # CIS 2.3.7.1 -- Do not display last user name
      begin
        output = `reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v DontDisplayLastUserName 2>nul`
        results['no_last_username_display'] = output.to_s.include?('0x1')
      rescue StandardError
        results['no_last_username_display'] = false
      end

      # CIS 2.3.8.1 -- SMB signing required (client)
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters" /v RequireSecuritySignature 2>nul`
        results['smb_signing_required_client'] = output.to_s.include?('0x1')
      rescue StandardError
        results['smb_signing_required_client'] = false
      end

      # CIS 2.3.9.1 -- SMB signing required (server)
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters" /v RequireSecuritySignature 2>nul`
        results['smb_signing_required_server'] = output.to_s.include?('0x1')
      rescue StandardError
        results['smb_signing_required_server'] = false
      end

      # CIS 2.3.10.2 -- Restrict anonymous SAM enumeration
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v RestrictAnonymousSAM 2>nul`
        results['restrict_anonymous_sam'] = output.to_s.include?('0x1')
      rescue StandardError
        results['restrict_anonymous_sam'] = false
      end

      # CIS 18.9.84.1 -- WinRM basic auth disabled (client)
      begin
        output = `reg query "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client" /v AllowBasic 2>nul`
        results['winrm_basic_auth_disabled_client'] = output.to_s.include?('0x0')
      rescue StandardError
        results['winrm_basic_auth_disabled_client'] = false
      end

      # CIS 18.9.85.1 -- WinRM basic auth disabled (service)
      begin
        output = `reg query "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service" /v AllowBasic 2>nul`
        results['winrm_basic_auth_disabled_service'] = output.to_s.include?('0x0')
      rescue StandardError
        results['winrm_basic_auth_disabled_service'] = false
      end

      # CIS 18.4.5 -- IP source routing disabled
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" /v DisableIPSourceRouting 2>nul`
        results['ip_source_routing_disabled'] = output.to_s.include?('0x2')
      rescue StandardError
        results['ip_source_routing_disabled'] = false
      end

      # CIS 2.3.1.4 -- Blank password use limited to console only
      begin
        output = `reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v LimitBlankPasswordUse 2>nul`
        results['blank_password_console_only'] = output.to_s.include?('0x1')
      rescue StandardError
        results['blank_password_console_only'] = false
      end
    end

    # ================================================================
    # Calculate aggregate compliance score
    # ================================================================
    check_results = results.select { |_k, v| v == true || v == false }
    total = check_results.length
    passed = check_results.values.count(true)
    failed = total - passed

    results['checks_passed'] = passed
    results['checks_total'] = total
    results['checks_failed'] = failed
    results['score'] = "#{passed}/#{total}"
    results['score_percent'] = total > 0 ? ((passed.to_f / total) * 100).round : 0
    results['compliant'] = (passed == total) && total > 0

    # Timestamp for when this fact was last evaluated
    results['last_checked'] = Time.now.utc.strftime('%Y-%m-%dT%H:%M:%SZ')

    results
  end
end
