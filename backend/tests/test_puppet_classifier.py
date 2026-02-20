"""Tests for app.services.puppet_classifier — pure-function classification logic.

All tests are synchronous and require no database, Redis, or external services.
"""

from app.services.puppet_classifier import (
    ALL_NODES_GROUP_ID,
    build_node_group_config,
    get_certname,
    get_node_classification_data,
    get_role_class,
)

# ---------------------------------------------------------------------------
# get_role_class
# ---------------------------------------------------------------------------


class TestGetRoleClass:
    def test_role_class_base(self):
        assert get_role_class("base") == "role::base"

    def test_role_class_web_server(self):
        assert get_role_class("web_server") == "role::web_server"

    def test_role_class_db_server(self):
        assert get_role_class("db_server") == "role::db_server"

    def test_role_class_app_server(self):
        assert get_role_class("app_server") == "role::app_server"

    def test_role_class_unknown_fallback(self):
        assert get_role_class("unknown_role") == "role::base"


# ---------------------------------------------------------------------------
# get_certname
# ---------------------------------------------------------------------------


class TestGetCertname:
    def test_certname_lowercase(self):
        assert get_certname("PROD-WEB-a3f8") == "prod-web-a3f8.anvilops.internal"

    def test_certname_custom_domain(self):
        assert get_certname("myhost", domain="example.com") == "myhost.example.com"

    def test_certname_already_lowercase(self):
        assert get_certname("dev-app-1234") == "dev-app-1234.anvilops.internal"


# ---------------------------------------------------------------------------
# build_node_group_config
# ---------------------------------------------------------------------------


class TestBuildNodeGroupConfig:
    def test_node_group_config_structure(self):
        config = build_node_group_config("web_server", "production")
        expected_keys = {"name", "parent", "environment", "classes", "description"}
        assert set(config.keys()) == expected_keys

    def test_node_group_config_parent(self):
        config = build_node_group_config("web_server", "production")
        assert config["parent"] == ALL_NODES_GROUP_ID

    def test_node_group_config_classes(self):
        config = build_node_group_config("web_server", "production")
        assert config["classes"] == {"role::web_server": {}}

    def test_node_group_config_name(self):
        config = build_node_group_config("web_server", "production")
        assert config["name"] == "AnvilOps - role::web_server"


# ---------------------------------------------------------------------------
# get_node_classification_data
# ---------------------------------------------------------------------------


class TestGetNodeClassificationData:
    def test_classification_data_full(self):
        server_data = {
            "puppet_role": "web_server",
            "environment": "staging",
            "server_name": "STG-WEB-01",
        }
        result = get_node_classification_data(server_data)

        assert result["certname"] == "stg-web-01.anvilops.internal"
        assert result["role_class"] == "role::web_server"
        assert result["environment"] == "staging"
        assert result["node_group_config"]["name"] == "AnvilOps - role::web_server"
        assert result["node_group_config"]["environment"] == "staging"
        assert result["node_group_config"]["classes"] == {"role::web_server": {}}

    def test_classification_data_defaults(self):
        """An empty dict should fall back to safe defaults."""
        result = get_node_classification_data({})

        assert result["certname"] == "unknown.anvilops.internal"
        assert result["role_class"] == "role::base"
        assert result["environment"] == "production"
        assert result["node_group_config"]["name"] == "AnvilOps - role::base"
        assert result["node_group_config"]["environment"] == "production"
