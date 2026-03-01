"""Unit tests for the synchronous database helpers in app.services.db.

All SQLAlchemy session interactions are fully mocked so no real database
connection is required.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.db import (
    _build_sync_url,
    create_build_steps,
    get_server_request,
    get_sync_db,
    update_build_step,
    update_server_status,
)

# ---------------------------------------------------------------------------
# _build_sync_url
# ---------------------------------------------------------------------------


class TestBuildSyncUrl:
    def test_replaces_asyncpg_with_psycopg2(self):
        url = "postgresql+asyncpg://user:pass@localhost/db"
        result = _build_sync_url(url)
        assert "psycopg2" in result
        assert "asyncpg" not in result

    def test_bare_postgresql_scheme_gets_psycopg2_driver(self):
        url = "postgresql://user:pass@localhost/db"
        result = _build_sync_url(url)
        assert result.startswith("postgresql+psycopg2://")

    def test_already_psycopg2_url_unchanged(self):
        url = "postgresql+psycopg2://user:pass@localhost/db"
        result = _build_sync_url(url)
        assert result == url

    def test_preserves_host_and_credentials(self):
        url = "postgresql+asyncpg://admin:secret@myhost:5432/mydb"
        result = _build_sync_url(url)
        assert "admin:secret@myhost:5432/mydb" in result


# ---------------------------------------------------------------------------
# get_sync_db context manager
# ---------------------------------------------------------------------------


class TestGetSyncDb:
    def _make_session(self):
        session = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        session.close = MagicMock()
        return session

    def test_yields_session_and_commits(self):
        session = self._make_session()
        with patch("app.services.db.SyncSessionLocal", return_value=session):
            with get_sync_db() as db:
                assert db is session
        session.commit.assert_called_once()
        session.close.assert_called_once()

    def test_rollback_on_exception(self):
        session = self._make_session()
        with patch("app.services.db.SyncSessionLocal", return_value=session):
            with pytest.raises(ValueError):
                with get_sync_db() as _db:
                    raise ValueError("boom")
        session.rollback.assert_called_once()
        session.close.assert_called_once()

    def test_close_called_even_after_exception(self):
        session = self._make_session()
        with patch("app.services.db.SyncSessionLocal", return_value=session):
            try:
                with get_sync_db():
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        session.close.assert_called_once()


# ---------------------------------------------------------------------------
# get_server_request
# ---------------------------------------------------------------------------


class TestGetServerRequest:
    def _make_server_request(self, **overrides):
        sr = MagicMock()
        sr.id = uuid4()
        sr.server_name = "TEST-WEB-01"
        sr.environment = "dev"
        sr.os_type = "amazon_linux_2023"
        sr.instance_size = "small"
        sr.region = "us-east-1"
        sr.vpc_id = "vpc-111"
        sr.subnet_id = "subnet-222"
        sr.security_profile = "internal_only"
        sr.domain_join = False
        sr.puppet_role = "web_server"
        sr.software_packages = ["nginx"]
        sr.additional_storage = []
        sr.tags = {"env": "dev"}
        sr.status = "approved"
        sr.status_message = None
        sr.aws_instance_id = None
        sr.private_ip = None
        sr.public_ip = None
        sr.dns_name = None
        for key, value in overrides.items():
            setattr(sr, key, value)
        return sr

    def test_returns_dict_with_expected_keys(self):
        sr = self._make_server_request()
        session = MagicMock()
        session.get = MagicMock(return_value=sr)

        result = get_server_request(session, str(sr.id))

        expected_keys = {
            "id", "server_name", "environment", "os_type", "instance_size",
            "region", "vpc_id", "subnet_id", "security_profile", "domain_join",
            "puppet_role", "software_packages", "additional_storage", "tags",
            "status", "status_message", "aws_instance_id", "private_ip",
            "public_ip", "dns_name", "awx_host_id", "puppet_certname", "cmdb_sys_id",
        }
        assert set(result.keys()) == expected_keys

    def test_id_is_string(self):
        sr = self._make_server_request()
        session = MagicMock()
        session.get = MagicMock(return_value=sr)
        result = get_server_request(session, str(sr.id))
        assert isinstance(result["id"], str)

    def test_returns_correct_values(self):
        sr = self._make_server_request(server_name="PROD-DB-01", status="building")
        session = MagicMock()
        session.get = MagicMock(return_value=sr)
        result = get_server_request(session, str(sr.id))
        assert result["server_name"] == "PROD-DB-01"
        assert result["status"] == "building"

    def test_raises_value_error_when_not_found(self):
        session = MagicMock()
        session.get = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="ServerRequest not found"):
            get_server_request(session, "nonexistent-id")


# ---------------------------------------------------------------------------
# update_server_status
# ---------------------------------------------------------------------------


class TestUpdateServerStatus:
    def _make_sr(self):
        sr = MagicMock()
        sr.status = "approved"
        sr.updated_at = None
        sr.aws_instance_id = None
        sr.private_ip = None
        return sr

    def test_updates_status(self):
        sr = self._make_sr()
        session = MagicMock()
        session.get = MagicMock(return_value=sr)
        update_server_status(session, "sr-id", "building")
        assert sr.status == "building"

    def test_updates_extra_kwargs(self):
        sr = self._make_sr()
        session = MagicMock()
        session.get = MagicMock(return_value=sr)
        update_server_status(
            session, "sr-id", "complete",
            aws_instance_id="i-abc", private_ip="10.0.0.1",
        )
        assert sr.aws_instance_id == "i-abc"
        assert sr.private_ip == "10.0.0.1"

    def test_updated_at_set(self):
        sr = self._make_sr()
        session = MagicMock()
        session.get = MagicMock(return_value=sr)
        update_server_status(session, "sr-id", "complete")
        assert sr.updated_at is not None

    def test_unknown_kwarg_ignored(self):
        """setattr is guarded by hasattr so unknown fields must not raise."""
        sr = MagicMock(spec=["status", "updated_at"])
        session = MagicMock()
        session.get = MagicMock(return_value=sr)
        # nonexistent_field is not on the spec so hasattr returns False
        update_server_status(session, "sr-id", "complete", nonexistent_field="value")
        # No AttributeError raised

    def test_noop_when_not_found(self, caplog):
        import logging

        session = MagicMock()
        session.get = MagicMock(return_value=None)
        with caplog.at_level(logging.ERROR):
            update_server_status(session, "missing-id", "complete")
        assert "ServerRequest not found" in caplog.text


# ---------------------------------------------------------------------------
# update_build_step
# ---------------------------------------------------------------------------


class TestUpdateBuildStep:
    def _make_step(self):
        step = MagicMock()
        step.status = "pending"
        step.updated_at = None
        step.output = None
        return step

    def test_updates_status(self):
        step = self._make_step()
        session = MagicMock()
        session.get = MagicMock(return_value=step)
        update_build_step(session, "step-id", "running")
        assert step.status == "running"

    def test_updates_extra_kwargs(self):
        step = self._make_step()
        session = MagicMock()
        session.get = MagicMock(return_value=step)
        update_build_step(session, "step-id", "complete", output="Apply complete!")
        assert step.output == "Apply complete!"

    def test_updated_at_set(self):
        step = self._make_step()
        session = MagicMock()
        session.get = MagicMock(return_value=step)
        update_build_step(session, "step-id", "complete")
        assert step.updated_at is not None

    def test_noop_when_not_found(self, caplog):
        import logging

        session = MagicMock()
        session.get = MagicMock(return_value=None)
        with caplog.at_level(logging.ERROR):
            update_build_step(session, "missing-step", "complete")
        assert "BuildStep not found" in caplog.text


# ---------------------------------------------------------------------------
# create_build_steps
# ---------------------------------------------------------------------------


class TestCreateBuildSteps:
    def test_creates_correct_number_of_steps(self):
        session = MagicMock()
        session.flush = MagicMock()
        steps = ["terraform", "awx", "puppet", "validation"]
        result = create_build_steps(session, "sr-001", steps)
        assert len(result) == 4
        assert session.add.call_count == 4

    def test_step_order_starts_at_1(self):
        session = MagicMock()
        session.flush = MagicMock()
        steps = ["terraform", "awx"]
        create_build_steps(session, "sr-001", steps)
        added_steps = [call[0][0] for call in session.add.call_args_list]
        orders = [s.step_order for s in added_steps]
        assert orders[0] == 1
        assert orders[1] == 2

    def test_returns_list_of_dicts_with_id_and_step_name(self):
        session = MagicMock()
        session.flush = MagicMock()
        result = create_build_steps(session, "sr-001", ["terraform"])
        assert "id" in result[0]
        assert "step_name" in result[0]
        assert result[0]["step_name"] == "terraform"

    def test_ids_are_strings(self):
        session = MagicMock()
        session.flush = MagicMock()
        result = create_build_steps(session, "sr-001", ["terraform", "awx"])
        for item in result:
            assert isinstance(item["id"], str)

    def test_flush_called(self):
        session = MagicMock()
        session.flush = MagicMock()
        create_build_steps(session, "sr-001", ["terraform"])
        session.flush.assert_called_once()

    def test_empty_steps_list_creates_nothing(self):
        session = MagicMock()
        session.flush = MagicMock()
        result = create_build_steps(session, "sr-001", [])
        assert result == []
        session.add.assert_not_called()
        session.flush.assert_called_once()

    def test_step_status_defaults_to_pending(self):
        session = MagicMock()
        session.flush = MagicMock()
        create_build_steps(session, "sr-001", ["terraform"])
        added = session.add.call_args[0][0]
        assert added.status == "pending"

    def test_server_request_id_assigned(self):
        session = MagicMock()
        session.flush = MagicMock()
        create_build_steps(session, "my-server-request-id", ["terraform"])
        added = session.add.call_args[0][0]
        assert added.server_request_id == "my-server-request-id"
