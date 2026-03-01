"""Unit tests for the CMDBSyncService.

Tests the interaction between CMDBSyncService and ServiceNowClient.
All ServiceNowClient calls are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.cmdb_sync import CMDBSyncService
from app.services.servicenow import ServiceNowClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_client() -> MagicMock:
    """Build a MagicMock with the ServiceNowClient interface."""
    mock = MagicMock(spec=ServiceNowClient)
    mock._map_status.side_effect = lambda s: {
        "ready": (1, 1),
        "pending": (2, 5),
        "failed": (2, 6),
        "decommissioned": (6, 7),
    }.get(s, (2, 5))
    mock._map_os_type.side_effect = lambda t: {
        "amazon_linux_2023": "Amazon Linux 2023",
        "windows_2022": "Windows Server 2022",
    }.get(t, t)
    mock._map_environment.side_effect = lambda e: {
        "dev": "Development",
        "staging": "Stage",
        "production": "Production",
    }.get(e, e)
    return mock


@pytest.fixture
def mock_client() -> MagicMock:
    return _make_mock_client()


@pytest.fixture
def service(mock_client: MagicMock) -> CMDBSyncService:
    return CMDBSyncService(client=mock_client)


@pytest.fixture
def server_data() -> dict:
    return {
        "server_name": "web-prod-01",
        "private_ip": "10.0.1.50",
        "dns_name": "web-prod-01.example.com",
        "os_type": "amazon_linux_2023",
        "environment": "production",
        "status": "ready",
        "puppet_certname": "web-prod-01.example.com",
        "aws_instance_id": "i-0123456789abcdef0",
        "region": "us-east-1",
    }


# ---------------------------------------------------------------------------
# sync_server_created
# ---------------------------------------------------------------------------


class TestSyncServerCreated:
    def test_creates_ci_when_none_exists(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = None
        mock_client.create_ci.return_value = {
            "sys_id": "new_sys_id",
            "ci_number": "CI0001",
            "result": {},
        }

        result = service.sync_server_created(server_data)

        assert result is not None
        assert result["action"] == "created"
        assert result["sys_id"] == "new_sys_id"
        assert result["ci_number"] == "CI0001"
        assert result["server_name"] == "web-prod-01"
        mock_client.create_ci.assert_called_once()

    def test_updates_ci_when_already_exists(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = {"sys_id": "existing_sys_id"}
        mock_client.update_ci.return_value = {"sys_id": "existing_sys_id", "result": {}}

        result = service.sync_server_created(server_data)

        assert result is not None
        assert result["action"] == "updated"
        assert result["sys_id"] == "existing_sys_id"
        mock_client.create_ci.assert_not_called()
        mock_client.update_ci.assert_called_once()

    def test_returns_none_when_create_fails(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = None
        mock_client.create_ci.return_value = None

        result = service.sync_server_created(server_data)

        assert result is None

    def test_returns_none_when_update_of_existing_fails(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = {"sys_id": "existing"}
        mock_client.update_ci.return_value = None

        result = service.sync_server_created(server_data)

        assert result is None

    def test_handles_exception_from_client(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.side_effect = RuntimeError("network error")

        result = service.sync_server_created(server_data)

        assert result is None

    def test_server_name_defaults_to_unknown(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        mock_client.find_ci_by_name.return_value = None
        mock_client.create_ci.return_value = {"sys_id": "s1", "ci_number": "", "result": {}}

        result = service.sync_server_created({})

        assert result is not None
        mock_client.find_ci_by_name.assert_called_with("unknown")


# ---------------------------------------------------------------------------
# sync_server_updated
# ---------------------------------------------------------------------------


class TestSyncServerUpdated:
    def test_updates_ci_with_known_sys_id(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.update_ci.return_value = {"sys_id": "known_id", "result": {}}

        result = service.sync_server_updated(server_data, "known_id")

        assert result is not None
        assert result["action"] == "updated"
        assert result["sys_id"] == "known_id"
        mock_client.update_ci.assert_called_once_with(
            "known_id", mock_client.update_ci.call_args[0][1]
        )

    def test_looks_up_ci_when_no_sys_id_provided(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = {"sys_id": "found_id"}
        mock_client.update_ci.return_value = {"sys_id": "found_id", "result": {}}

        result = service.sync_server_updated(server_data, "")

        assert result is not None
        mock_client.find_ci_by_name.assert_called_once_with("web-prod-01")
        mock_client.update_ci.assert_called_once()

    def test_creates_ci_when_not_found_by_name(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = None
        # sync_server_created path
        mock_client.create_ci.return_value = {
            "sys_id": "brand_new", "ci_number": "CI9", "result": {}
        }

        result = service.sync_server_updated(server_data, "")

        # Should have fallen through to sync_server_created
        assert result is not None
        assert result["action"] == "created"

    def test_returns_none_when_update_fails(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.update_ci.return_value = None

        result = service.sync_server_updated(server_data, "sys123")

        assert result is None

    def test_handles_exception_from_update(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.update_ci.side_effect = RuntimeError("DB error")

        result = service.sync_server_updated(server_data, "sys123")

        assert result is None


# ---------------------------------------------------------------------------
# sync_server_decommissioned
# ---------------------------------------------------------------------------


class TestSyncServerDecommissioned:
    def test_retires_ci_with_known_sys_id(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.retire_ci.return_value = {"sys_id": "retire_id", "result": {}}

        result = service.sync_server_decommissioned(server_data, "retire_id")

        assert result is not None
        assert result["action"] == "retired"
        assert result["sys_id"] == "retire_id"

    def test_looks_up_ci_by_name_when_no_sys_id(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = {"sys_id": "found_for_retire"}
        mock_client.retire_ci.return_value = {"sys_id": "found_for_retire", "result": {}}

        result = service.sync_server_decommissioned(server_data, "")

        mock_client.find_ci_by_name.assert_called_once()
        assert result["action"] == "retired"

    def test_returns_none_when_ci_not_found_by_name(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.find_ci_by_name.return_value = None

        result = service.sync_server_decommissioned(server_data, "")

        assert result is None
        mock_client.retire_ci.assert_not_called()

    def test_returns_none_when_retire_fails(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.retire_ci.return_value = None

        result = service.sync_server_decommissioned(server_data, "sys123")

        assert result is None

    def test_handles_exception_from_retire(
        self, service: CMDBSyncService, mock_client: MagicMock, server_data: dict
    ):
        mock_client.retire_ci.side_effect = RuntimeError("retire error")

        result = service.sync_server_decommissioned(server_data, "sys123")

        assert result is None


# ---------------------------------------------------------------------------
# full_sync
# ---------------------------------------------------------------------------


class TestFullSync:
    def _make_server(self, name: str, status: str, sys_id: str = "") -> dict:
        return {"server_name": name, "status": status, "cmdb_sys_id": sys_id}

    def test_empty_servers_returns_zero_stats(self, service: CMDBSyncService):
        stats = service.full_sync([])
        assert stats["total"] == 0
        assert stats["created"] == 0
        assert stats["updated"] == 0
        assert stats["retired"] == 0
        assert stats["failed"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == []

    def test_pending_servers_are_skipped(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        servers = [self._make_server("srv-1", "pending")]
        stats = service.full_sync(servers)
        assert stats["skipped"] == 1
        assert stats["created"] == 0
        mock_client.create_ci.assert_not_called()

    def test_decommissioned_with_sys_id_is_retired(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        mock_client.retire_ci.return_value = {"sys_id": "d1", "result": {}}
        servers = [self._make_server("srv-2", "decommissioned", sys_id="d1")]
        stats = service.full_sync(servers)
        assert stats["retired"] == 1

    def test_decommissioned_without_sys_id_is_skipped(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        servers = [self._make_server("srv-3", "decommissioned", sys_id="")]
        stats = service.full_sync(servers)
        assert stats["skipped"] == 1

    def test_ready_server_with_sys_id_is_updated(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        mock_client.update_ci.return_value = {"sys_id": "u1", "result": {}}
        servers = [self._make_server("srv-4", "ready", sys_id="u1")]
        stats = service.full_sync(servers)
        assert stats["updated"] == 1

    def test_ready_server_without_sys_id_is_created(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        mock_client.find_ci_by_name.return_value = None
        mock_client.create_ci.return_value = {"sys_id": "c1", "ci_number": "CI1", "result": {}}
        servers = [self._make_server("srv-5", "ready", sys_id="")]
        stats = service.full_sync(servers)
        assert stats["created"] == 1

    def test_failed_create_increments_failed_counter(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        mock_client.find_ci_by_name.return_value = None
        mock_client.create_ci.return_value = None
        servers = [self._make_server("srv-6", "ready", sys_id="")]
        stats = service.full_sync(servers)
        assert stats["failed"] == 1

    def test_mixed_batch_stats(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        mock_client.find_ci_by_name.return_value = None
        mock_client.create_ci.return_value = {"sys_id": "n1", "ci_number": "CI", "result": {}}
        mock_client.update_ci.return_value = {"sys_id": "e1", "result": {}}
        mock_client.retire_ci.return_value = {"sys_id": "r1", "result": {}}

        servers = [
            self._make_server("srv-a", "pending"),          # skipped
            self._make_server("srv-b", "ready", sys_id=""), # created
            self._make_server("srv-c", "ready", sys_id="e1"),  # updated
            self._make_server("srv-d", "decommissioned", sys_id="r1"),  # retired
        ]
        stats = service.full_sync(servers)

        assert stats["total"] == 4
        assert stats["skipped"] == 1
        assert stats["created"] == 1
        assert stats["updated"] == 1
        assert stats["retired"] == 1
        assert stats["failed"] == 0

    def test_synced_at_is_present(self, service: CMDBSyncService):
        stats = service.full_sync([])
        assert "synced_at" in stats
        assert stats["synced_at"]  # non-empty

    def test_exception_during_server_increments_failed(
        self, service: CMDBSyncService, mock_client: MagicMock
    ):
        # Patch sync_server_created directly so the exception propagates to full_sync's
        # outer try/except (find_ci_by_name raises inside sync_server_created which
        # catches it internally and returns None; we need to escape that layer).
        with patch.object(service, "sync_server_created", side_effect=RuntimeError("boom")):
            servers = [self._make_server("srv-err", "ready", sys_id="")]
            stats = service.full_sync(servers)
        assert stats["failed"] == 1
        assert len(stats["errors"]) == 1
        assert stats["errors"][0]["server_name"] == "srv-err"


# ---------------------------------------------------------------------------
# _build_ci_updates
# ---------------------------------------------------------------------------


class TestBuildCiUpdates:
    def test_build_ci_updates_includes_status_fields(
        self, service: CMDBSyncService, server_data: dict
    ):
        updates = service._build_ci_updates(server_data)
        assert "operational_status" in updates
        assert "install_status" in updates
        assert updates["operational_status"] == "1"
        assert updates["install_status"] == "1"

    def test_build_ci_updates_maps_os_type(
        self, service: CMDBSyncService, server_data: dict
    ):
        updates = service._build_ci_updates(server_data)
        assert updates["os"] == "Amazon Linux 2023"

    def test_build_ci_updates_maps_environment(
        self, service: CMDBSyncService, server_data: dict
    ):
        updates = service._build_ci_updates(server_data)
        assert updates["environment"] == "Production"

    def test_build_ci_updates_omits_empty_optional_fields(self, service: CMDBSyncService):
        data = {"server_name": "srv", "status": "ready"}
        updates = service._build_ci_updates(data)
        # No ip_address, dns_name, etc. should appear
        assert "ip_address" not in updates
        assert "dns_domain" not in updates

    def test_build_ci_updates_includes_aws_fields_when_present(
        self, service: CMDBSyncService, server_data: dict
    ):
        updates = service._build_ci_updates(server_data)
        assert updates["u_aws_instance_id"] == "i-0123456789abcdef0"
        assert updates["u_aws_region"] == "us-east-1"
        assert updates["u_puppet_certname"] == "web-prod-01.example.com"
