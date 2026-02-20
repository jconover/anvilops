"""Unit tests for the categorize_drift function in drift_monitor.

All tests exercise pure in-memory logic -- no database, Redis,
or external API connections are required.
"""

import pytest

from app.services.drift_monitor import categorize_drift


# ------------------------------------------------------------------
# SSH configuration -- critical security (CIS-5.2.8)
# ------------------------------------------------------------------


class TestSSHConfigCritical:
    """SSH-related file changes must be classified as critical security drift."""

    def test_ssh_config_critical(self):
        """Full path /etc/ssh/sshd_config with content property."""
        category, severity, cis_id = categorize_drift(
            "File", "/etc/ssh/sshd_config", "content"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id == "CIS-5.2.8"

    def test_sshd_config_by_title(self):
        """Short title sshd_config with mode property still matches SSH rule."""
        category, severity, cis_id = categorize_drift(
            "File", "sshd_config", "mode"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id == "CIS-5.2.8"


# ------------------------------------------------------------------
# Firewall -- critical security (CIS-3.5.1)
# ------------------------------------------------------------------


class TestFirewallCritical:
    """Firewall-related file changes must be classified as critical security drift."""

    def test_firewall_iptables(self):
        """iptables configuration file change."""
        category, severity, cis_id = categorize_drift(
            "File", "/etc/sysconfig/iptables", "content"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id == "CIS-3.5.1"

    def test_firewall_nftables(self):
        """nftables configuration file change."""
        category, severity, cis_id = categorize_drift(
            "File", "nftables", "content"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id == "CIS-3.5.1"


# ------------------------------------------------------------------
# Audit configuration -- critical security (CIS-4.1.1)
# ------------------------------------------------------------------


class TestAuditConfigCritical:
    def test_audit_config(self):
        """auditd.conf change must be critical security with CIS-4.1.1."""
        category, severity, cis_id = categorize_drift(
            "File", "/etc/audit/auditd.conf", "content"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id == "CIS-4.1.1"


# ------------------------------------------------------------------
# PAM / password policy -- critical security (CIS-5.3.1)
# ------------------------------------------------------------------


class TestPAMConfigCritical:
    def test_pam_config(self):
        """PAM system-auth change must be critical security with CIS-5.3.1."""
        category, severity, cis_id = categorize_drift(
            "File", "/etc/pam.d/system-auth", "content"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id == "CIS-5.3.1"


# ------------------------------------------------------------------
# Sudoers -- high security (CIS-5.2.1)
# ------------------------------------------------------------------


class TestSudoersHigh:
    def test_sudoers(self):
        """sudoers file change must be high security with CIS-5.2.1."""
        category, severity, cis_id = categorize_drift(
            "File", "/etc/sudoers", "content"
        )
        assert category == "security"
        assert severity == "high"
        assert cis_id == "CIS-5.2.1"


# ------------------------------------------------------------------
# Windows security policy -- critical security (no CIS mapping)
# ------------------------------------------------------------------


class TestWindowsSecurityPolicy:
    def test_windows_security_policy(self):
        """Windows secpol.inf change must be critical security with no CIS ID."""
        category, severity, cis_id = categorize_drift(
            "File", "secpol.inf", "content"
        )
        assert category == "security"
        assert severity == "critical"
        assert cis_id is None


# ------------------------------------------------------------------
# SELinux / augeas -- high security
# ------------------------------------------------------------------


class TestGenericSecurityResources:
    def test_selinux_resource(self):
        """SELinux resource type must be classified as high security."""
        category, severity, cis_id = categorize_drift(
            "Selinux", "enforcing", "mode"
        )
        assert category == "security"
        assert severity == "high"
        assert cis_id is None


# ------------------------------------------------------------------
# Service state changes -- high
# ------------------------------------------------------------------


class TestServiceChanges:
    def test_service_state(self):
        """Service resource type must be classified as high service drift."""
        category, severity, cis_id = categorize_drift(
            "Service", "httpd", "ensure"
        )
        assert category == "service"
        assert severity == "high"
        assert cis_id is None

    def test_windows_service(self):
        """Windows_service resource type must also be high service drift."""
        category, severity, cis_id = categorize_drift(
            "Windows_service", "wuauserv", "ensure"
        )
        assert category == "service"
        assert severity == "high"
        assert cis_id is None


# ------------------------------------------------------------------
# Package changes -- medium
# ------------------------------------------------------------------


class TestPackageChanges:
    def test_package_change(self):
        """Package resource type must be classified as medium package drift."""
        category, severity, cis_id = categorize_drift(
            "Package", "openssl", "ensure"
        )
        assert category == "package"
        assert severity == "medium"
        assert cis_id is None


# ------------------------------------------------------------------
# Registry / cron -- medium configuration
# ------------------------------------------------------------------


class TestConfigurationChanges:
    def test_registry_key(self):
        """Registry_key resource must be medium configuration drift."""
        category, severity, cis_id = categorize_drift(
            "Registry_key", "HKLM\\Software\\test", "ensure"
        )
        assert category == "configuration"
        assert severity == "medium"
        assert cis_id is None


# ------------------------------------------------------------------
# Generic file changes
# ------------------------------------------------------------------


class TestGenericFileChanges:
    def test_file_content_change(self):
        """File with content property must be medium file drift."""
        category, severity, cis_id = categorize_drift(
            "File", "/etc/app/config.yml", "content"
        )
        assert category == "file"
        assert severity == "medium"
        assert cis_id is None

    def test_file_generic_property(self):
        """File with unrecognized property must be low file drift."""
        category, severity, cis_id = categorize_drift(
            "File", "/tmp/somefile", "mtime"
        )
        assert category == "file"
        assert severity == "low"
        assert cis_id is None


# ------------------------------------------------------------------
# Default fallback
# ------------------------------------------------------------------


class TestDefaultFallback:
    def test_unknown_resource_default(self):
        """Completely unknown resource type falls back to low configuration."""
        category, severity, cis_id = categorize_drift(
            "Exec", "/usr/bin/something", "returns"
        )
        assert category == "configuration"
        assert severity == "low"
        assert cis_id is None
