"""Unit tests for AWX helper functions.

All tests exercise pure in-memory logic -- no database, Redis,
or external API connections are required.
"""

from app.services.awx import (
    LINUX_CONNECTION_VARS,
    WINDOWS_CONNECTION_VARS,
    AWXService,
    _is_windows,
    _os_family,
)

# ------------------------------------------------------------------
# _is_windows
# ------------------------------------------------------------------


class TestIsWindows:
    """Verify OS type detection for Windows vs Linux."""

    def test_is_windows_true(self):
        """os_type containing 'windows' should return True."""
        assert _is_windows("windows_2022") is True

    def test_is_windows_false(self):
        """os_type without 'windows' should return False."""
        assert _is_windows("ubuntu_2204") is False

    def test_is_windows_case_insensitive(self):
        """Detection must be case-insensitive."""
        assert _is_windows("Windows_2019") is True


# ------------------------------------------------------------------
# _os_family
# ------------------------------------------------------------------


class TestOsFamily:
    """Verify OS family derivation from os_type strings."""

    def test_os_family_linux(self):
        """Non-Windows os_type must return 'linux'."""
        assert _os_family("amazon_linux_2023") == "linux"

    def test_os_family_windows(self):
        """Windows os_type must return 'windows'."""
        assert _os_family("windows_2022") == "windows"


# ------------------------------------------------------------------
# AWXService._resolve_template_names
# ------------------------------------------------------------------


class TestResolveTemplateNames:
    """Verify the ordered list of AWX job template names."""

    def test_resolve_templates_linux_basic(self):
        """Linux with no domain join and no packages: base + deploy-agents only."""
        result = AWXService._resolve_template_names(
            os_family="linux",
            domain_join=False,
            software_packages=[],
        )
        assert result == [
            "anvilops-linux-base",
            "anvilops-deploy-agents",
        ]

    def test_resolve_templates_windows_full(self):
        """Windows with domain join and packages: all four templates in order."""
        result = AWXService._resolve_template_names(
            os_family="windows",
            domain_join=True,
            software_packages=["iis"],
        )
        assert result == [
            "anvilops-windows-base",
            "anvilops-domain-join",
            "anvilops-install-software",
            "anvilops-deploy-agents",
        ]


# ------------------------------------------------------------------
# Connection variable constants
# ------------------------------------------------------------------


class TestConnectionConstants:
    """Verify the default connection variables are set correctly."""

    def test_linux_connection_vars(self):
        """Linux defaults: SSH on port 22 with ec2-user."""
        assert LINUX_CONNECTION_VARS["ansible_connection"] == "ssh"
        assert LINUX_CONNECTION_VARS["ansible_port"] == 22
        assert LINUX_CONNECTION_VARS["ansible_user"] == "ec2-user"

    def test_windows_connection_vars(self):
        """Windows defaults: WinRM on port 5986."""
        assert WINDOWS_CONNECTION_VARS["ansible_connection"] == "winrm"
        assert WINDOWS_CONNECTION_VARS["ansible_port"] == 5986
