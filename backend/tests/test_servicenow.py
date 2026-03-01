"""Unit tests for the ServiceNow CMDB integration service.

All external HTTP calls are mocked -- no real ServiceNow instance required.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.servicenow import (
    _OS_TYPE_MAP,
    _STATUS_MAP,
    ServiceNowClient,
    get_servicenow_client,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> ServiceNowClient:
    return ServiceNowClient(
        instance_url="https://dev12345.service-now.com",
        username="svc_anvilops",
        password="secret",
        enabled=True,
        table="cmdb_ci_server",
    )


@pytest.fixture
def disabled_client() -> ServiceNowClient:
    return ServiceNowClient(
        instance_url="https://dev12345.service-now.com",
        username="svc_anvilops",
        password="secret",
        enabled=False,
    )


@pytest.fixture
def server_data() -> dict:
    return {
        "server_name": "web-prod-01",
        "private_ip": "10.0.1.50",
        "dns_name": "web-prod-01.example.com",
        "os_type": "amazon_linux_2023",
        "environment": "production",
        "status": "ready",
        "requester": "jdoe@example.com",
        "puppet_certname": "web-prod-01.example.com",
        "aws_instance_id": "i-0123456789abcdef0",
        "region": "us-east-1",
    }


def _mock_httpx_response(status_code: int, json_body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = str(json_body)
    return resp


# ---------------------------------------------------------------------------
# OS type mapping
# ---------------------------------------------------------------------------


class TestOsTypeMapping:
    def test_known_os_types_map_correctly(self, client: ServiceNowClient):
        assert client._map_os_type("windows_2022") == "Windows Server 2022"
        assert client._map_os_type("windows_2019") == "Windows Server 2019"
        assert client._map_os_type("amazon_linux_2023") == "Amazon Linux 2023"
        assert client._map_os_type("ubuntu_2204") == "Ubuntu 22.04 LTS"
        assert client._map_os_type("rhel_9") == "Red Hat Enterprise Linux 9"

    def test_unknown_os_type_returns_raw_value(self, client: ServiceNowClient):
        assert client._map_os_type("custom_os_99") == "custom_os_99"

    def test_empty_os_type_returns_empty(self, client: ServiceNowClient):
        assert client._map_os_type("") == ""

    def test_all_os_types_in_map(self):
        assert len(_OS_TYPE_MAP) == 5


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------


class TestStatusMapping:
    def test_ready_maps_to_operational(self, client: ServiceNowClient):
        op_status, inst_status = client._map_status("ready")
        assert op_status == 1
        assert inst_status == 1

    def test_decommissioned_maps_to_retired(self, client: ServiceNowClient):
        op_status, inst_status = client._map_status("decommissioned")
        assert op_status == 6
        assert inst_status == 7

    def test_failed_maps_to_pending_repair(self, client: ServiceNowClient):
        op_status, inst_status = client._map_status("failed")
        assert op_status == 2
        assert inst_status == 6

    def test_building_status_maps_to_non_operational(self, client: ServiceNowClient):
        op_status, inst_status = client._map_status("building")
        assert op_status == 2
        assert inst_status == 5

    def test_unknown_status_falls_back_to_default(self, client: ServiceNowClient):
        op_status, inst_status = client._map_status("unknown_status_xyz")
        assert op_status == 2
        assert inst_status == 5

    def test_all_defined_statuses_present(self):
        expected = {
            "pending", "approved", "building", "provisioning",
            "configuring", "validating", "ready", "failed",
            "decommissioning", "decommissioned",
        }
        assert set(_STATUS_MAP.keys()) == expected


# ---------------------------------------------------------------------------
# Environment mapping
# ---------------------------------------------------------------------------


class TestEnvironmentMapping:
    def test_dev_maps_to_development(self):
        assert ServiceNowClient._map_environment("dev") == "Development"

    def test_staging_maps_to_stage(self):
        assert ServiceNowClient._map_environment("staging") == "Stage"

    def test_production_maps_to_production(self):
        assert ServiceNowClient._map_environment("production") == "Production"

    def test_unknown_environment_returned_as_is(self):
        assert ServiceNowClient._map_environment("qa") == "qa"

    def test_empty_environment_returned_as_empty(self):
        assert ServiceNowClient._map_environment("") == ""


# ---------------------------------------------------------------------------
# _check_enabled
# ---------------------------------------------------------------------------


class TestCheckEnabled:
    def test_disabled_client_returns_false(self, disabled_client: ServiceNowClient):
        assert disabled_client._check_enabled("any_method") is False

    def test_missing_instance_url_returns_false(self):
        c = ServiceNowClient(instance_url="", username="u", password="p", enabled=True)
        assert c._check_enabled("any_method") is False

    def test_missing_username_returns_false(self):
        c = ServiceNowClient(
            instance_url="https://example.service-now.com",
            username="",
            password="p",
            enabled=True,
        )
        assert c._check_enabled("any_method") is False

    def test_fully_configured_returns_true(self, client: ServiceNowClient):
        assert client._check_enabled("any_method") is True


# ---------------------------------------------------------------------------
# create_ci
# ---------------------------------------------------------------------------


class TestCreateCi:
    def test_create_ci_returns_sys_id_on_success(
        self, client: ServiceNowClient, server_data: dict
    ):
        mock_resp = _mock_httpx_response(
            201,
            {"result": {"sys_id": "abc123", "asset_tag": "CI0001234"}},
        )
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.create_ci(server_data)

        assert result is not None
        assert result["sys_id"] == "abc123"
        assert result["ci_number"] == "CI0001234"
        assert "result" in result

    def test_create_ci_payload_maps_fields(
        self, client: ServiceNowClient, server_data: dict
    ):
        mock_resp = _mock_httpx_response(
            201,
            {"result": {"sys_id": "xyz789", "asset_tag": ""}},
        )
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client.create_ci(server_data)
            call_kwargs = mock_http.request.call_args.kwargs
            sent_payload = call_kwargs["json"]

        assert sent_payload["name"] == "web-prod-01"
        assert sent_payload["os"] == "Amazon Linux 2023"
        assert sent_payload["environment"] == "Production"
        assert sent_payload["operational_status"] == "1"
        assert sent_payload["install_status"] == "1"
        assert sent_payload["assigned_to"] == "jdoe@example.com"
        assert sent_payload["u_aws_instance_id"] == "i-0123456789abcdef0"

    def test_create_ci_omits_assigned_to_when_no_requester(
        self, client: ServiceNowClient, server_data: dict
    ):
        data = dict(server_data)
        del data["requester"]

        mock_resp = _mock_httpx_response(201, {"result": {"sys_id": "s1"}})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client.create_ci(data)
            sent = mock_http.request.call_args.kwargs["json"]

        assert "assigned_to" not in sent

    def test_create_ci_uses_sys_id_as_ci_number_when_no_asset_tag(
        self, client: ServiceNowClient, server_data: dict
    ):
        mock_resp = _mock_httpx_response(
            201, {"result": {"sys_id": "fallback_id", "asset_tag": ""}},
        )
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.create_ci(server_data)

        assert result["ci_number"] == "fallback_id"

    def test_create_ci_returns_none_when_http_fails(
        self, client: ServiceNowClient, server_data: dict
    ):
        mock_resp = _mock_httpx_response(500, {})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.create_ci(server_data)

        assert result is None

    def test_create_ci_returns_none_when_disabled(
        self, disabled_client: ServiceNowClient, server_data: dict
    ):
        result = disabled_client.create_ci(server_data)
        assert result is None


# ---------------------------------------------------------------------------
# update_ci
# ---------------------------------------------------------------------------


class TestUpdateCi:
    def test_update_ci_success(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(200, {"result": {"sys_id": "abc123"}})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.update_ci("abc123", {"operational_status": "1"})

        assert result is not None
        assert result["sys_id"] == "abc123"

    def test_update_ci_empty_sys_id_returns_none(self, client: ServiceNowClient):
        result = client.update_ci("", {"foo": "bar"})
        assert result is None

    def test_update_ci_returns_none_on_http_error(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(404, {})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.update_ci("missing_sys_id", {})

        assert result is None

    def test_update_ci_returns_none_when_disabled(self, disabled_client: ServiceNowClient):
        result = disabled_client.update_ci("abc123", {})
        assert result is None


# ---------------------------------------------------------------------------
# retire_ci
# ---------------------------------------------------------------------------


class TestRetireCi:
    def test_retire_ci_sends_retired_status(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(200, {"result": {"sys_id": "retire_id"}})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.retire_ci("retire_id")
            sent = mock_http.request.call_args.kwargs["json"]

        assert result is not None
        assert sent["operational_status"] == "6"
        assert sent["install_status"] == "7"
        assert "Decommissioned" in sent["short_description"]

    def test_retire_ci_empty_sys_id_returns_none(self, client: ServiceNowClient):
        result = client.retire_ci("")
        assert result is None

    def test_retire_ci_returns_none_on_error(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(500, {})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.retire_ci("sys123")

        assert result is None


# ---------------------------------------------------------------------------
# get_ci
# ---------------------------------------------------------------------------


class TestGetCi:
    def test_get_ci_returns_record(self, client: ServiceNowClient):
        record = {"sys_id": "abc", "name": "web-prod-01"}
        mock_resp = _mock_httpx_response(200, {"result": record})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.get_ci("abc")

        assert result == record

    def test_get_ci_empty_sys_id_returns_none(self, client: ServiceNowClient):
        assert client.get_ci("") is None

    def test_get_ci_http_error_returns_none(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(404, {})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.get_ci("bad_id")

        assert result is None


# ---------------------------------------------------------------------------
# find_ci_by_name
# ---------------------------------------------------------------------------


class TestFindCiByName:
    def test_find_ci_by_name_returns_first_record(self, client: ServiceNowClient):
        records = [{"sys_id": "r1", "name": "web-prod-01"}]
        mock_resp = _mock_httpx_response(200, {"result": records})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.find_ci_by_name("web-prod-01")

        assert result == records[0]

    def test_find_ci_by_name_empty_results_returns_none(
        self, client: ServiceNowClient
    ):
        mock_resp = _mock_httpx_response(200, {"result": []})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.find_ci_by_name("nonexistent-server")

        assert result is None

    def test_find_ci_by_name_empty_name_returns_none(self, client: ServiceNowClient):
        result = client.find_ci_by_name("")
        assert result is None

    def test_find_ci_by_name_passes_correct_query(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(200, {"result": [{"sys_id": "x"}]})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            client.find_ci_by_name("my-server")
            params = mock_http.request.call_args.kwargs["params"]

        assert "name=my-server" in params["sysparm_query"]
        assert params["sysparm_limit"] == "1"


# ---------------------------------------------------------------------------
# get_ci_relationships
# ---------------------------------------------------------------------------


class TestGetCiRelationships:
    def test_returns_relationships(self, client: ServiceNowClient):
        rels = [{"sys_id": "rel1", "parent": "abc", "child": "def"}]
        mock_resp = _mock_httpx_response(200, {"result": rels})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.get_ci_relationships("abc")

        assert result == rels

    def test_empty_sys_id_returns_empty_list(self, client: ServiceNowClient):
        assert client.get_ci_relationships("") == []

    def test_http_error_returns_empty_list(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(500, {})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client.get_ci_relationships("sys123")

        assert result == []

    def test_disabled_client_returns_empty_list(self, disabled_client: ServiceNowClient):
        assert disabled_client.get_ci_relationships("abc") == []


# ---------------------------------------------------------------------------
# _request error handling
# ---------------------------------------------------------------------------


class TestRequestErrorHandling:
    def test_timeout_exception_returns_none(self, client: ServiceNowClient):
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.side_effect = httpx.TimeoutException("timed out")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client._request("GET", "/api/now/table/cmdb_ci_server")

        assert result is None

    def test_http_error_returns_none(self, client: ServiceNowClient):
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.side_effect = httpx.HTTPError("connection error")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client._request("GET", "/api/now/table/cmdb_ci_server")

        assert result is None

    def test_unexpected_exception_returns_none(self, client: ServiceNowClient):
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.side_effect = RuntimeError("unexpected")
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client._request("GET", "/api/now/table/cmdb_ci_server")

        assert result is None

    def test_4xx_response_returns_none(self, client: ServiceNowClient):
        mock_resp = _mock_httpx_response(401, {})
        with patch("httpx.Client") as mock_client_cls:
            mock_http = MagicMock()
            mock_http.request.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_http

            result = client._request("GET", "/api/now/table/cmdb_ci_server")

        assert result is None


# ---------------------------------------------------------------------------
# get_servicenow_client factory
# ---------------------------------------------------------------------------


class TestGetServiceNowClient:
    def test_factory_returns_client_instance(self):
        # settings is imported inside get_servicenow_client, so patch at app.core.config
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SERVICENOW_INSTANCE_URL = "https://test.service-now.com"
            mock_settings.SERVICENOW_USERNAME = "admin"
            mock_settings.SERVICENOW_PASSWORD = "pass"
            mock_settings.SERVICENOW_ENABLED = True
            mock_settings.SERVICENOW_TABLE = "cmdb_ci_server"

            client = get_servicenow_client()

        assert isinstance(client, ServiceNowClient)
        assert client.instance_url == "https://test.service-now.com"
        assert client.enabled is True
