"""Unit tests for app.api.v1.servers — server name generation and helpers.

The endpoint tests in this file focus on the pure utility functions
(``generate_server_name``, ``ENV_ABBREV``, ``ROLE_ABBREV``) that do not
require a database or Celery.
"""

from unittest.mock import patch

from app.api.v1.servers import ENV_ABBREV, ROLE_ABBREV, generate_server_name

# ---------------------------------------------------------------------------
# ENV_ABBREV / ROLE_ABBREV lookup tables
# ---------------------------------------------------------------------------


class TestEnvAbbrev:
    def test_dev_maps_to_dev(self):
        assert ENV_ABBREV["dev"] == "DEV"

    def test_staging_maps_to_stg(self):
        assert ENV_ABBREV["staging"] == "STG"

    def test_production_maps_to_prod(self):
        assert ENV_ABBREV["production"] == "PROD"


class TestRoleAbbrev:
    def test_base_maps_to_srv(self):
        assert ROLE_ABBREV["base"] == "SRV"

    def test_web_server_maps_to_web(self):
        assert ROLE_ABBREV["web_server"] == "WEB"

    def test_db_server_maps_to_db(self):
        assert ROLE_ABBREV["db_server"] == "DB"

    def test_app_server_maps_to_app(self):
        assert ROLE_ABBREV["app_server"] == "APP"

    def test_dev_workstation_maps_to_dev(self):
        assert ROLE_ABBREV["dev_workstation"] == "DEV"


# ---------------------------------------------------------------------------
# generate_server_name
# ---------------------------------------------------------------------------


class TestGenerateServerName:
    def test_format_is_env_role_suffix(self):
        name = generate_server_name("dev", "web_server")
        parts = name.split("-")
        assert len(parts) == 3
        assert parts[0] == "DEV"
        assert parts[1] == "WEB"
        assert len(parts[2]) == 4  # hex(2) = 4 chars

    def test_production_app_server(self):
        name = generate_server_name("production", "app_server")
        assert name.startswith("PROD-APP-")

    def test_staging_db_server(self):
        name = generate_server_name("staging", "db_server")
        assert name.startswith("STG-DB-")

    def test_unknown_env_falls_back_to_srv(self):
        name = generate_server_name("unknown_env", "web_server")
        assert name.startswith("SRV-WEB-")

    def test_unknown_role_falls_back_to_srv(self):
        name = generate_server_name("dev", "unknown_role")
        assert name.startswith("DEV-SRV-")

    def test_suffix_is_random(self):
        names = {generate_server_name("dev", "base") for _ in range(10)}
        # With 4-char hex, collisions in 10 tries are astronomically unlikely
        assert len(names) > 1

    @patch("app.api.v1.servers.secrets.token_hex", return_value="abcd")
    def test_deterministic_with_mock(self, _mock_hex):
        name = generate_server_name("production", "web_server")
        assert name == "PROD-WEB-abcd"
