"""Tests for application configuration (app.core.config).

Validates that the Settings class loads defaults correctly and that
environment variable overrides are applied as expected.
"""

from unittest.mock import patch


class TestSettingsDefaults:
    """Verify that Settings has sensible defaults for all fields."""

    def test_database_url_default(self):
        from app.core.config import Settings

        s = Settings()
        assert "postgresql+asyncpg" in s.DATABASE_URL
        assert "anvilops" in s.DATABASE_URL

    def test_redis_url_default(self):
        from app.core.config import Settings

        s = Settings()
        assert s.REDIS_URL.startswith("redis://")

    def test_aws_default_region(self):
        from app.core.config import Settings

        s = Settings()
        assert s.AWS_DEFAULT_REGION == "us-east-1"

    def test_allowed_regions_default(self):
        from app.core.config import Settings

        s = Settings()
        assert "us-east-1" in s.ALLOWED_REGIONS
        assert "us-west-2" in s.ALLOWED_REGIONS

    def test_api_v1_prefix(self):
        from app.core.config import Settings

        s = Settings()
        assert s.API_V1_PREFIX == "/api/v1"

    def test_project_name(self):
        from app.core.config import Settings

        s = Settings()
        assert s.PROJECT_NAME == "AnvilOps"

    def test_debug_default_false(self):
        from app.core.config import Settings

        s = Settings()
        assert s.DEBUG is False

    def test_cors_origins_default_empty(self):
        from app.core.config import Settings

        s = Settings()
        assert s.CORS_ORIGINS == []

    def test_awx_defaults(self):
        from app.core.config import Settings

        s = Settings()
        assert s.AWX_BASE_URL == "http://awx:8052"
        assert s.AWX_VERIFY_SSL is True
        assert s.AWX_JOB_TIMEOUT == 600
        assert s.AWX_POLL_INTERVAL == 10
        assert s.AWX_ORGANIZATION_ID == 1

    def test_puppet_defaults(self):
        from app.core.config import Settings

        s = Settings()
        assert s.PUPPET_BASE_URL == "https://puppet:8140"
        assert s.PUPPET_VERIFY_SSL is True
        assert s.PUPPET_CA_PORT == 8140
        assert s.PUPPET_CLASSIFIER_PORT == 4433
        assert s.PUPPET_PUPPETDB_PORT == 8081
        assert s.PUPPET_ORCHESTRATOR_PORT == 8143
        assert s.PUPPET_NODE_CHECKIN_TIMEOUT == 600
        assert s.PUPPET_NODE_CHECKIN_POLL == 30
        assert s.PUPPET_DEFAULT_ENVIRONMENT == "production"
        assert s.PUPPET_CERTNAME_DOMAIN == "anvilops.internal"

    def test_slack_defaults(self):
        from app.core.config import Settings

        s = Settings()
        assert s.SLACK_ENABLED is False
        assert s.SLACK_CHANNEL == "#anvilops-builds"

    def test_servicenow_defaults(self):
        from app.core.config import Settings

        s = Settings()
        assert s.SERVICENOW_ENABLED is False
        assert s.SERVICENOW_TABLE == "cmdb_ci_server"

    def test_model_config_extra_ignore(self):
        from app.core.config import Settings

        assert Settings.model_config["extra"] == "ignore"


class TestSettingsEnvOverride:
    """Verify that environment variables override defaults."""

    def test_debug_override(self):
        from app.core.config import Settings

        with patch.dict("os.environ", {"DEBUG": "true"}, clear=False):
            s = Settings()
        assert s.DEBUG is True

    def test_aws_region_override(self):
        from app.core.config import Settings

        with patch.dict("os.environ", {"AWS_DEFAULT_REGION": "eu-west-1"}, clear=False):
            s = Settings()
        assert s.AWS_DEFAULT_REGION == "eu-west-1"

    def test_project_name_override(self):
        from app.core.config import Settings

        with patch.dict("os.environ", {"PROJECT_NAME": "TestOps"}, clear=False):
            s = Settings()
        assert s.PROJECT_NAME == "TestOps"

    def test_slack_enabled_override(self):
        from app.core.config import Settings

        with patch.dict("os.environ", {"SLACK_ENABLED": "true"}, clear=False):
            s = Settings()
        assert s.SLACK_ENABLED is True


class TestSettingsSingleton:
    """Verify the module-level settings instance."""

    def test_settings_instance_exists(self):
        from app.core.config import settings

        assert settings is not None
        assert settings.PROJECT_NAME == "AnvilOps"
