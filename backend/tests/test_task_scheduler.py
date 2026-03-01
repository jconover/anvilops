"""Unit tests for scheduler task helper functions.

Tests _generate_server_name (pure function) and related constants.
No DB or Celery connections required.
"""


from app.tasks.scheduler import _ENV_ABBREV, _ROLE_ABBREV, _generate_server_name

# ---------------------------------------------------------------------------
# _ENV_ABBREV / _ROLE_ABBREV constants
# ---------------------------------------------------------------------------


class TestEnvAbbrev:
    def test_dev_maps_to_DEV(self):
        assert _ENV_ABBREV["dev"] == "DEV"

    def test_staging_maps_to_STG(self):
        assert _ENV_ABBREV["staging"] == "STG"

    def test_production_maps_to_PROD(self):
        assert _ENV_ABBREV["production"] == "PROD"


class TestRoleAbbrev:
    def test_base_maps_to_SRV(self):
        assert _ROLE_ABBREV["base"] == "SRV"

    def test_web_server_maps_to_WEB(self):
        assert _ROLE_ABBREV["web_server"] == "WEB"

    def test_db_server_maps_to_DB(self):
        assert _ROLE_ABBREV["db_server"] == "DB"

    def test_app_server_maps_to_APP(self):
        assert _ROLE_ABBREV["app_server"] == "APP"

    def test_dev_workstation_maps_to_DEV(self):
        assert _ROLE_ABBREV["dev_workstation"] == "DEV"


# ---------------------------------------------------------------------------
# _generate_server_name
# ---------------------------------------------------------------------------


class TestGenerateServerName:
    def test_format_is_ENV_ROLE_suffix(self):
        name = _generate_server_name("dev", "web_server")
        parts = name.split("-")
        assert len(parts) == 3
        assert parts[0] == "DEV"
        assert parts[1] == "WEB"
        # suffix is 4 hex chars (2 bytes)
        assert len(parts[2]) == 4

    def test_dev_env_web_role(self):
        name = _generate_server_name("dev", "web_server")
        assert name.startswith("DEV-WEB-")

    def test_production_env_db_role(self):
        name = _generate_server_name("production", "db_server")
        assert name.startswith("PROD-DB-")

    def test_staging_env_app_role(self):
        name = _generate_server_name("staging", "app_server")
        assert name.startswith("STG-APP-")

    def test_unknown_env_falls_back_to_SRV(self):
        name = _generate_server_name("unknown_env", "web_server")
        assert name.startswith("SRV-WEB-")

    def test_unknown_role_falls_back_to_SRV(self):
        name = _generate_server_name("dev", "unknown_role")
        assert name.startswith("DEV-SRV-")

    def test_suffix_is_lowercase_hex(self):
        name = _generate_server_name("dev", "web_server")
        suffix = name.split("-")[2]
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_suffix_is_4_chars(self):
        name = _generate_server_name("dev", "base")
        suffix = name.split("-")[2]
        assert len(suffix) == 4

    def test_names_are_unique(self):
        """Two calls should produce different suffixes (with overwhelming probability)."""
        names = {_generate_server_name("dev", "web_server") for _ in range(10)}
        # With 2 bytes of entropy (65536 possibilities), 10 names are almost
        # certainly unique.
        assert len(names) > 1

    def test_base_role_dev_env(self):
        name = _generate_server_name("dev", "base")
        assert name.startswith("DEV-SRV-")

    def test_dev_workstation_role(self):
        name = _generate_server_name("dev", "dev_workstation")
        assert name.startswith("DEV-DEV-")

    def test_empty_env_falls_back_to_SRV(self):
        name = _generate_server_name("", "web_server")
        assert name.startswith("SRV-WEB-")

    def test_empty_role_falls_back_to_SRV(self):
        name = _generate_server_name("dev", "")
        assert name.startswith("DEV-SRV-")
