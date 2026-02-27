"""Unit tests for the Puppet Enterprise service layer.

Covers both async (PuppetEnterpriseService) and sync
(PuppetEnterpriseServiceSync) clients, plus the _build_url helper.

All external HTTP calls are replaced with unittest.mock objects so no
real Puppet Enterprise instance is required.
"""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.puppet import (
    PuppetEnterpriseService,
    PuppetEnterpriseServiceSync,
    _build_url,
)
from app.services.puppet_exceptions import (
    PuppetAuthError,
    PuppetClassificationError,
    PuppetConnectionError,
    PuppetError,
    PuppetTimeoutError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int = 200, json_data=None, text: str = "") -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text or ""
    resp.json.return_value = json_data if json_data is not None else {}
    resp.headers = {}
    return resp


def _patch_async_client(puppet_svc: PuppetEnterpriseService, responses=None, side_effect=None):
    """
    Patch _get_client() on an async service instance to return a controlled mock.

    Pass either:
      - responses: a single mock response or list of mock responses
      - side_effect: an exception (or list) to raise on request()
    Returns the mock client.
    """
    mock_client = AsyncMock()

    if side_effect is not None:
        mock_client.request.side_effect = side_effect
    elif isinstance(responses, list):
        mock_client.request.side_effect = responses
    elif responses is not None:
        mock_client.request.return_value = responses

    async def _fake_get_client():
        return mock_client

    puppet_svc._get_client = _fake_get_client
    return mock_client


# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_standard_https(self):
        result = _build_url("https://puppet.example.com", 4433, "/classifier-api/v1/groups")
        assert result == "https://puppet.example.com:4433/classifier-api/v1/groups"

    def test_strips_existing_port(self):
        result = _build_url("https://puppet.example.com:8140", 8081, "/pdb/query/v4/nodes")
        assert result == "https://puppet.example.com:8081/pdb/query/v4/nodes"

    def test_uses_https_scheme(self):
        result = _build_url("https://puppet.host", 8143, "/orchestrator/v1/command/deploy")
        assert result.startswith("https://")

    def test_path_appended_correctly(self):
        result = _build_url("https://host", 4433, "/some/path")
        assert result.endswith("/some/path")


# ---------------------------------------------------------------------------
# PuppetEnterpriseService (async)
# ---------------------------------------------------------------------------


@pytest.fixture
def puppet_svc():
    """Async PuppetEnterpriseService with dummy credentials."""
    return PuppetEnterpriseService(
        base_url="https://puppet.test",
        token="test-token",
        verify_ssl=False,
        timeout=5.0,
    )


class TestPuppetEnterpriseServiceInit:
    def test_base_url_stored(self, puppet_svc):
        assert puppet_svc.base_url == "https://puppet.test"

    def test_token_stored(self, puppet_svc):
        assert puppet_svc.token == "test-token"

    def test_verify_ssl_stored(self, puppet_svc):
        assert puppet_svc.verify_ssl is False

    def test_auth_header_set(self, puppet_svc):
        assert puppet_svc._headers["X-Authentication"] == "test-token"


class TestPuppetEnterpriseServiceUrlBuilders:
    def test_classifier_url(self, puppet_svc):
        url = puppet_svc._classifier_url("/groups")
        assert "/classifier-api/v1/groups" in url

    def test_puppetdb_url(self, puppet_svc):
        url = puppet_svc._puppetdb_url("/nodes")
        assert "/pdb/query/v4/nodes" in url

    def test_orchestrator_url(self, puppet_svc):
        url = puppet_svc._orchestrator_url("/command/deploy")
        assert "/orchestrator/v1/command/deploy" in url

    def test_ca_url(self, puppet_svc):
        url = puppet_svc._ca_url("/certificate_status/mynode")
        assert "/puppet-ca/v1/certificate_status/mynode" in url


class TestPuppetEnterpriseServiceRequest:
    @pytest.mark.asyncio
    async def test_request_raises_connection_error_on_connect_failure(self, puppet_svc):
        _patch_async_client(puppet_svc, side_effect=httpx.ConnectError("refused"))
        with pytest.raises(PuppetConnectionError, match="Cannot connect"):
            await puppet_svc._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    @pytest.mark.asyncio
    async def test_request_raises_connection_error_on_timeout(self, puppet_svc):
        _patch_async_client(puppet_svc, side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(PuppetConnectionError, match="timed out"):
            await puppet_svc._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    @pytest.mark.asyncio
    async def test_request_raises_auth_error_on_401(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(401, text="Unauthorized"))
        with pytest.raises(PuppetAuthError):
            await puppet_svc._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    @pytest.mark.asyncio
    async def test_request_raises_auth_error_on_403(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(403, text="Forbidden"))
        with pytest.raises(PuppetAuthError):
            await puppet_svc._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    @pytest.mark.asyncio
    async def test_request_raises_puppet_error_on_500(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(500, text="Server Error"))
        with pytest.raises(PuppetError):
            await puppet_svc._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    @pytest.mark.asyncio
    async def test_request_returns_response_on_200(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data={"ok": True}))
        resp = await puppet_svc._request("GET", "https://puppet.test:8081/pdb/query/v4/version")
        assert resp.status_code == 200


class TestPuppetEnterpriseServiceHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(200))
        result = await puppet_svc.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self, puppet_svc):
        _patch_async_client(puppet_svc, side_effect=httpx.ConnectError("refused"))
        result = await puppet_svc.health_check()
        assert result is False


class TestPuppetEnterpriseServiceNodeGroups:
    @pytest.mark.asyncio
    async def test_get_node_groups_returns_list(self, puppet_svc):
        groups = [{"id": "abc", "name": "All Nodes"}]
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=groups))
        result = await puppet_svc.get_node_groups()
        assert result == groups

    @pytest.mark.asyncio
    async def test_find_node_group_by_name_found(self, puppet_svc):
        groups = [
            {"id": "aaa", "name": "Group A"},
            {"id": "bbb", "name": "Target Group"},
        ]
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=groups))
        result = await puppet_svc.find_node_group_by_name("Target Group")
        assert result == {"id": "bbb", "name": "Target Group"}

    @pytest.mark.asyncio
    async def test_find_node_group_by_name_not_found(self, puppet_svc):
        groups = [{"id": "aaa", "name": "Group A"}]
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=groups))
        result = await puppet_svc.find_node_group_by_name("Missing Group")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_id(self, puppet_svc):
        """If the group already exists, returns its id without a POST."""
        existing = [{"id": "existing-id", "name": "AnvilOps - role::web"}]
        mock_client = _patch_async_client(
            puppet_svc,
            responses=_make_response(200, json_data=existing),
        )
        result = await puppet_svc.get_or_create_node_group(
            name="AnvilOps - role::web",
            parent_id="parent-id",
            environment="production",
            classes={"role::web": {}},
        )
        assert result == "existing-id"
        # Only one GET call should have been made (no POST)
        assert mock_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_group(self, puppet_svc):
        """If the group does not exist, POST creates it and returns new id."""
        created = {"id": "new-group-id", "name": "AnvilOps - role::db"}
        _patch_async_client(puppet_svc, responses=[
            _make_response(200, json_data=[]),       # GET /groups (not found)
            _make_response(201, json_data=created),  # POST /groups (create)
        ])
        result = await puppet_svc.get_or_create_node_group(
            name="AnvilOps - role::db",
            parent_id="parent-id",
            environment="production",
            classes={"role::db": {}},
        )
        assert result == "new-group-id"

    @pytest.mark.asyncio
    async def test_get_or_create_handles_303_redirect(self, puppet_svc):
        """A 303 redirect response extracts the id from the Location header."""
        resp_303 = _make_response(303, json_data={})
        resp_303.headers = {"location": "/classifier-api/v1/groups/redirect-id"}
        _patch_async_client(puppet_svc, responses=[
            _make_response(200, json_data=[]),  # GET (not found)
            resp_303,                           # POST (303 redirect)
        ])
        result = await puppet_svc.get_or_create_node_group(
            name="New Group",
            parent_id="parent",
            environment="production",
            classes={},
        )
        assert result == "redirect-id"

    @pytest.mark.asyncio
    async def test_get_or_create_raises_on_missing_id(self, puppet_svc):
        """If neither Location nor id is present, PuppetClassificationError is raised."""
        _patch_async_client(puppet_svc, responses=[
            _make_response(200, json_data=[]),   # GET (not found)
            _make_response(201, json_data={}),   # POST returns no id
        ])
        with pytest.raises(PuppetClassificationError):
            await puppet_svc.get_or_create_node_group(
                name="Bad Group",
                parent_id="parent",
                environment="production",
                classes={},
            )


class TestPuppetEnterpriseServiceClassifyNode:
    @pytest.mark.asyncio
    async def test_classify_node_returns_pinned_on_204(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(204, text=""))
        result = await puppet_svc.classify_node("node.example.com", "group-id-123")
        assert result["pinned"] is True
        assert result["certname"] == "node.example.com"

    @pytest.mark.asyncio
    async def test_classify_node_returns_json_on_200(self, puppet_svc):
        body = {"certname": "node.example.com", "node_group_id": "gid"}
        resp = _make_response(200, json_data=body, text='{"certname": "node.example.com"}')
        _patch_async_client(puppet_svc, responses=resp)
        result = await puppet_svc.classify_node("node.example.com", "gid")
        assert result == body


class TestPuppetEnterpriseServicePuppetDB:
    @pytest.mark.asyncio
    async def test_get_node_facts_returns_flat_dict(self, puppet_svc):
        facts_list = [
            {"name": "os", "value": "Linux", "certname": "n1"},
            {"name": "kernel", "value": "5.15", "certname": "n1"},
        ]
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=facts_list))
        result = await puppet_svc.get_node_facts("n1.example.com")
        assert result == {"os": "Linux", "kernel": "5.15"}

    @pytest.mark.asyncio
    async def test_get_node_report_slices_to_limit(self, puppet_svc):
        reports = [{"hash": f"h{i}", "status": "unchanged"} for i in range(5)]
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=reports))
        result = await puppet_svc.get_node_report("node.example.com", limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_node_status_returns_first_node(self, puppet_svc):
        nodes = [{"certname": "n1", "latest_report_status": "unchanged"}]
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=nodes))
        result = await puppet_svc.get_node_status("n1")
        assert result["certname"] == "n1"

    @pytest.mark.asyncio
    async def test_get_node_status_returns_empty_when_not_found(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=[]))
        result = await puppet_svc.get_node_status("unknown")
        assert result == {}


class TestPuppetEnterpriseServiceSignCertificate:
    @pytest.mark.asyncio
    async def test_sign_certificate_success(self, puppet_svc):
        _patch_async_client(puppet_svc, responses=_make_response(200))
        await puppet_svc.sign_certificate("node.example.com")  # Should not raise

    @pytest.mark.asyncio
    async def test_sign_certificate_idempotent_on_409(self, puppet_svc):
        """A 409 (already signed) should be silently ignored."""
        _patch_async_client(puppet_svc, responses=_make_response(409, text="Already signed"))
        await puppet_svc.sign_certificate("node.example.com")  # Should not raise

    @pytest.mark.asyncio
    async def test_sign_certificate_reraises_non_409(self, puppet_svc):
        """Errors other than 400/409 should propagate."""
        _patch_async_client(puppet_svc, responses=_make_response(500, text="Server Error"))
        with pytest.raises(PuppetError):
            await puppet_svc.sign_certificate("node.example.com")


class TestPuppetEnterpriseServiceRunPuppet:
    @pytest.mark.asyncio
    async def test_run_puppet_on_node_returns_job(self, puppet_svc):
        job = {"job": {"name": "orch-job-1", "state": "running"}}
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=job))
        result = await puppet_svc.run_puppet_on_node("node.example.com")
        assert result["job"]["name"] == "orch-job-1"


class TestPuppetEnterpriseServiceWaitForCheckin:
    @pytest.mark.asyncio
    async def test_wait_returns_node_status_when_checked_in(self, puppet_svc):
        node_status = {
            "certname": "n1",
            "catalog_timestamp": "2024-01-01T00:00:00Z",
            "latest_report_status": "unchanged",
        }
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=[node_status]))
        result = await puppet_svc.wait_for_node_checkin("n1", timeout=10, poll_interval=1)
        assert result["certname"] == "n1"
        assert result["catalog_timestamp"] == "2024-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_wait_raises_timeout_when_node_never_appears(self, puppet_svc):
        """Node never gets a catalog_timestamp -- should raise PuppetTimeoutError."""
        _patch_async_client(puppet_svc, responses=_make_response(200, json_data=[]))
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(PuppetTimeoutError, match="did not check in"):
                await puppet_svc.wait_for_node_checkin("n1", timeout=2, poll_interval=1)


class TestPuppetEnterpriseServiceEnrollNode:
    @pytest.mark.asyncio
    async def test_enroll_node_success(self, puppet_svc):
        """Full happy-path enrollment: group found, pinned, cert signed, run ok."""
        node_status = {
            "certname": "n1",
            "catalog_timestamp": "2024-01-01T00:00:00Z",
            "latest_report_status": "unchanged",
        }
        report = {"hash": "abc123", "status": "unchanged"}
        _patch_async_client(puppet_svc, responses=[
            _make_response(200, json_data=[{"id": "gid-1", "name": "AnvilOps - role::web_server"}]),
            _make_response(204, text=""),
            _make_response(200),
            _make_response(200, json_data=[node_status]),
            _make_response(200, json_data=[report]),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await puppet_svc.enroll_node("n1", "web_server")

        assert result["success"] is True
        assert result["certname"] == "n1"
        assert result["report_status"] == "unchanged"

    @pytest.mark.asyncio
    async def test_enroll_node_timeout_returns_failure(self, puppet_svc):
        """If wait_for_node_checkin times out, enroll_node returns success=False."""
        # timeout=2, poll_interval=1 → 2 poll iterations, each returns empty node list
        empty_node = _make_response(200, json_data=[])
        _patch_async_client(puppet_svc, responses=[
            _make_response(200, json_data=[{"id": "gid", "name": "AnvilOps - role::db_server"}]),
            _make_response(204, text=""),
            _make_response(200),
            empty_node, empty_node, empty_node,  # enough empties for the poll loop
        ])
        puppet_svc._checkin_timeout = 2
        puppet_svc._checkin_poll = 1
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await puppet_svc.enroll_node("n1", "db_server", environment="production")

        assert result["success"] is False
        assert result["report_status"] == "timeout"

    @pytest.mark.asyncio
    async def test_enroll_node_puppet_error_returns_failure(self, puppet_svc):
        """A PuppetError during enrollment is caught and returns success=False."""
        _patch_async_client(puppet_svc, side_effect=httpx.ConnectError("refused"))
        result = await puppet_svc.enroll_node("n1", "web_server")
        assert result["success"] is False
        assert result["report_status"] == "error"

    @pytest.mark.asyncio
    async def test_enroll_node_failed_report_status(self, puppet_svc):
        """A 'failed' report status results in success=False."""
        node_status = {
            "certname": "n1",
            "catalog_timestamp": "2024-01-01T00:00:00Z",
            "latest_report_status": "failed",
        }
        report = {"hash": "abc", "status": "failed"}
        _patch_async_client(puppet_svc, responses=[
            _make_response(200, json_data=[{"id": "gid", "name": "AnvilOps - role::web_server"}]),
            _make_response(204, text=""),
            _make_response(200),
            _make_response(200, json_data=[node_status]),
            _make_response(200, json_data=[report]),
        ])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await puppet_svc.enroll_node("n1", "web_server")

        assert result["success"] is False
        assert result["report_status"] == "failed"


class TestPuppetEnterpriseServicePurgeNode:
    @pytest.mark.asyncio
    async def test_purge_node_best_effort_all_succeed(self, puppet_svc):
        groups = [{"id": "g1"}, {"id": "g2"}]
        _patch_async_client(puppet_svc, responses=[
            _make_response(200),                    # deactivate POST
            _make_response(200, json_data=groups),  # GET groups
            _make_response(204, text=""),           # unpin g1
            _make_response(204, text=""),           # unpin g2
            _make_response(200),                    # revoke cert
            _make_response(200),                    # delete cert
        ])
        await puppet_svc.purge_node("old-node.example.com")

    @pytest.mark.asyncio
    async def test_purge_node_continues_on_error(self, puppet_svc):
        """If intermediate steps fail, the remaining steps still execute."""
        _patch_async_client(puppet_svc, responses=[
            httpx.ConnectError("deactivate failed"),  # deactivate fails (raised as side_effect)
            _make_response(200, json_data=[]),         # GET groups
            _make_response(200),                       # revoke
            _make_response(200),                       # delete
        ])
        # Should not raise even if the deactivate step fails
        await puppet_svc.purge_node("old-node.example.com")


# ---------------------------------------------------------------------------
# PuppetEnterpriseServiceSync (blocking, for Celery)
# ---------------------------------------------------------------------------


@pytest.fixture
def puppet_sync():
    """Sync PuppetEnterpriseServiceSync with a plain MagicMock for the http client."""
    svc = PuppetEnterpriseServiceSync.__new__(PuppetEnterpriseServiceSync)
    svc.base_url = "https://puppet.test"
    svc.token = "test-token"
    svc.verify_ssl = False
    svc._timeout = 5.0
    svc._headers = {"X-Authentication": "test-token", "Content-Type": "application/json"}
    svc._ca_port = 8140
    svc._classifier_port = 4433
    svc._puppetdb_port = 8081
    svc._orchestrator_port = 8143
    svc._checkin_timeout = 300
    svc._checkin_poll = 10
    svc._default_environment = "production"
    svc.client = MagicMock()  # plain MagicMock, not spec'd to httpx.Client
    return svc


class TestPuppetEnterpriseServiceSyncRequest:
    def test_request_raises_connection_error(self, puppet_sync):
        puppet_sync.client.request.side_effect = httpx.ConnectError("refused")
        with pytest.raises(PuppetConnectionError):
            puppet_sync._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    def test_request_raises_timeout_error(self, puppet_sync):
        puppet_sync.client.request.side_effect = httpx.TimeoutException("timeout")
        with pytest.raises(PuppetConnectionError, match="timed out"):
            puppet_sync._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    def test_request_raises_auth_error_on_401(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(401)
        with pytest.raises(PuppetAuthError):
            puppet_sync._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    def test_request_raises_puppet_error_on_500(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(500, text="err")
        with pytest.raises(PuppetError):
            puppet_sync._request("GET", "https://puppet.test:8081/pdb/query/v4/nodes")

    def test_request_returns_response_on_success(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(200, json_data={"v": 1})
        resp = puppet_sync._request("GET", "https://puppet.test:8081/pdb/query/v4/version")
        assert resp.status_code == 200


class TestPuppetEnterpriseServiceSyncHealthCheck:
    def test_health_check_true_on_200(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(200)
        assert puppet_sync.health_check() is True

    def test_health_check_false_on_error(self, puppet_sync):
        puppet_sync.client.request.side_effect = httpx.ConnectError("refused")
        assert puppet_sync.health_check() is False


class TestPuppetEnterpriseServiceSyncNodeGroups:
    def test_get_node_groups(self, puppet_sync):
        groups = [{"id": "g1", "name": "All Nodes"}]
        puppet_sync.client.request.return_value = _make_response(200, json_data=groups)
        assert puppet_sync.get_node_groups() == groups

    def test_find_node_group_by_name_found(self, puppet_sync):
        groups = [{"id": "g1", "name": "Target"}, {"id": "g2", "name": "Other"}]
        puppet_sync.client.request.return_value = _make_response(200, json_data=groups)
        result = puppet_sync.find_node_group_by_name("Target")
        assert result["id"] == "g1"

    def test_find_node_group_by_name_not_found(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(200, json_data=[])
        assert puppet_sync.find_node_group_by_name("Missing") is None

    def test_get_or_create_returns_existing(self, puppet_sync):
        existing = [{"id": "exist-id", "name": "MyGroup"}]
        puppet_sync.client.request.return_value = _make_response(200, json_data=existing)
        result = puppet_sync.get_or_create_node_group(
            name="MyGroup", parent_id="p", environment="production", classes={}
        )
        assert result == "exist-id"

    def test_get_or_create_creates_new(self, puppet_sync):
        puppet_sync.client.request.side_effect = [
            _make_response(200, json_data=[]),                    # GET (not found)
            _make_response(201, json_data={"id": "new-gid"}),    # POST (create)
        ]
        result = puppet_sync.get_or_create_node_group(
            name="NewGroup", parent_id="p", environment="production", classes={}
        )
        assert result == "new-gid"

    def test_get_or_create_raises_on_missing_id(self, puppet_sync):
        puppet_sync.client.request.side_effect = [
            _make_response(200, json_data=[]),   # GET (not found)
            _make_response(201, json_data={}),   # POST (no id)
        ]
        with pytest.raises(PuppetClassificationError):
            puppet_sync.get_or_create_node_group(
                name="BadGroup", parent_id="p", environment="production", classes={}
            )


class TestPuppetEnterpriseServiceSyncPuppetDB:
    def test_get_node_facts_returns_flat_dict(self, puppet_sync):
        facts_list = [
            {"name": "os", "value": "Linux"},
            {"name": "fqdn", "value": "n1.example.com"},
        ]
        puppet_sync.client.request.return_value = _make_response(200, json_data=facts_list)
        result = puppet_sync.get_node_facts("n1")
        assert result == {"os": "Linux", "fqdn": "n1.example.com"}

    def test_get_node_report_slices_to_limit(self, puppet_sync):
        reports = [{"hash": f"h{i}"} for i in range(10)]
        puppet_sync.client.request.return_value = _make_response(200, json_data=reports)
        result = puppet_sync.get_node_report("n1", limit=3)
        assert len(result) == 3

    def test_get_node_status_returns_first_node(self, puppet_sync):
        nodes = [{"certname": "n1", "latest_report_status": "unchanged"}]
        puppet_sync.client.request.return_value = _make_response(200, json_data=nodes)
        result = puppet_sync.get_node_status("n1")
        assert result["certname"] == "n1"

    def test_get_node_status_empty_when_not_found(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(200, json_data=[])
        assert puppet_sync.get_node_status("unknown") == {}


class TestPuppetEnterpriseServiceSyncSignCertificate:
    def test_sign_certificate_success(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(200)
        puppet_sync.sign_certificate("node.example.com")  # Should not raise

    def test_sign_certificate_idempotent_on_400(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(400, text="Already signed")
        puppet_sync.sign_certificate("node.example.com")  # Should not raise

    def test_sign_certificate_reraises_500(self, puppet_sync):
        puppet_sync.client.request.return_value = _make_response(500, text="err")
        with pytest.raises(PuppetError):
            puppet_sync.sign_certificate("node.example.com")


class TestPuppetEnterpriseServiceSyncClose:
    def test_close_calls_client_close(self, puppet_sync):
        puppet_sync.close()
        puppet_sync.client.close.assert_called_once()


# ---------------------------------------------------------------------------
# PuppetError exception attributes
# ---------------------------------------------------------------------------


class TestPuppetExceptions:
    def test_puppet_error_message(self):
        exc = PuppetError("Something failed", status_code=404)
        assert exc.message == "Something failed"
        assert exc.status_code == 404

    def test_puppet_auth_error_is_puppet_error(self):
        exc = PuppetAuthError("bad token", status_code=401)
        assert isinstance(exc, PuppetError)
        assert exc.status_code == 401

    def test_puppet_connection_error_is_puppet_error(self):
        exc = PuppetConnectionError("unreachable")
        assert isinstance(exc, PuppetError)

    def test_puppet_timeout_error_is_puppet_error(self):
        exc = PuppetTimeoutError("timeout")
        assert isinstance(exc, PuppetError)

    def test_puppet_classification_error_is_puppet_error(self):
        exc = PuppetClassificationError("group error")
        assert isinstance(exc, PuppetError)

    def test_puppet_error_repr_includes_status(self):
        exc = PuppetError("err", status_code=500)
        assert "500" in repr(exc)
