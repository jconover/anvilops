"""Unit tests for app.tasks.awx — AWX Celery tasks.

All external dependencies (AWX service, database) are mocked so these
tests run without infrastructure.
"""

from unittest.mock import MagicMock, patch

from app.tasks.awx import _get_awx_service, _summarise_jobs

# ---------------------------------------------------------------------------
# _summarise_jobs
# ---------------------------------------------------------------------------


class TestSummariseJobs:
    def test_empty_list(self):
        assert _summarise_jobs([]) == ""

    def test_single_success(self):
        jobs = [{"status": "successful", "template": "base-config", "job_id": 42}]
        result = _summarise_jobs(jobs)
        assert "[SUCCESSFUL]" in result
        assert "base-config" in result
        assert "42" in result

    def test_multiple_jobs(self):
        jobs = [
            {"status": "successful", "template": "t1", "job_id": 1},
            {"status": "failed", "template": "t2", "job_id": 2, "error": "timeout"},
        ]
        result = _summarise_jobs(jobs)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "[SUCCESSFUL]" in lines[0]
        assert "[FAILED]" in lines[1]
        assert "timeout" in lines[1]

    def test_missing_fields_use_defaults(self):
        jobs = [{}]
        result = _summarise_jobs(jobs)
        assert "[UNKNOWN]" in result
        assert "unknown" in result
        assert "n/a" in result


# ---------------------------------------------------------------------------
# _get_awx_service
# ---------------------------------------------------------------------------


class TestGetAwxService:
    @patch("app.tasks.awx.AWXServiceSync", None)
    def test_raises_when_awx_not_available(self):
        import pytest

        with pytest.raises(RuntimeError, match="AWXServiceSync is not available"):
            _get_awx_service()

    @patch("app.tasks.awx.settings")
    @patch("app.tasks.awx.AWXServiceSync")
    def test_constructs_service_with_settings(self, mock_cls, mock_settings):
        mock_settings.AWX_BASE_URL = "https://awx.example.com"
        mock_settings.AWX_USERNAME = "admin"
        mock_settings.AWX_PASSWORD = "secret"
        _get_awx_service()
        mock_cls.assert_called_once_with(
            base_url="https://awx.example.com",
            username="admin",
            password="secret",
            timeout=30.0,
        )


# ---------------------------------------------------------------------------
# awx_configure task
# ---------------------------------------------------------------------------


class TestAwxConfigureTask:
    @patch("app.tasks.awx._get_awx_service")
    @patch("app.tasks.awx.get_server_request")
    @patch("app.tasks.awx.get_sync_db")
    def test_successful_pipeline(self, mock_db, mock_get_sr, mock_get_awx):
        from app.tasks.awx import awx_configure

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sr.return_value = {
            "server_name": "PROD-WEB-a1b2",
            "private_ip": "10.0.0.1",
        }

        mock_awx = MagicMock()
        mock_awx.run_configuration_pipeline.return_value = {
            "success": True,
            "host_id": "h-123",
            "jobs": [{"status": "successful", "template": "t1", "job_id": 1}],
        }
        mock_get_awx.return_value = mock_awx

        result = awx_configure("sr-id")
        assert result["exit_code"] == 0
        assert "succeeded" in result["output"]
        assert result["host_id"] == "h-123"
        mock_awx.close.assert_called_once()

    @patch("app.tasks.awx._get_awx_service")
    @patch("app.tasks.awx.get_server_request")
    @patch("app.tasks.awx.get_sync_db")
    def test_failed_pipeline(self, mock_db, mock_get_sr, mock_get_awx):
        from app.tasks.awx import awx_configure

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sr.return_value = {"server_name": "DEV-SRV-x1y2"}

        mock_awx = MagicMock()
        mock_awx.run_configuration_pipeline.return_value = {
            "success": False,
            "host_id": None,
            "jobs": [],
        }
        mock_get_awx.return_value = mock_awx

        result = awx_configure("sr-id")
        assert result["exit_code"] == 1
        assert "FAILED" in result["output"]

    @patch("app.tasks.awx._get_awx_service")
    @patch("app.tasks.awx.get_server_request")
    @patch("app.tasks.awx.get_sync_db")
    def test_exception_returns_error_dict(self, mock_db, mock_get_sr, mock_get_awx):
        from app.tasks.awx import awx_configure

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sr.return_value = {"server_name": "test"}

        mock_awx = MagicMock()
        mock_awx.run_configuration_pipeline.side_effect = RuntimeError("connection refused")
        mock_get_awx.return_value = mock_awx

        result = awx_configure("sr-id")
        assert result["exit_code"] == 1
        assert "connection refused" in result["output"]
        assert result["jobs"] == []


# ---------------------------------------------------------------------------
# awx_decommission task
# ---------------------------------------------------------------------------


class TestAwxDecommissionTask:
    @patch("app.tasks.awx._get_awx_service")
    @patch("app.tasks.awx.get_server_request")
    @patch("app.tasks.awx.get_sync_db")
    def test_no_host_id_skips_cleanup(self, mock_db, mock_get_sr, _mock_awx):
        from app.tasks.awx import awx_decommission

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sr.return_value = {"server_name": "test", "awx_host_id": None}

        result = awx_decommission("sr-id")
        assert result["exit_code"] == 0
        assert "skipping" in result["output"].lower()

    @patch("app.tasks.awx._get_awx_service")
    @patch("app.tasks.awx.get_server_request")
    @patch("app.tasks.awx.get_sync_db")
    def test_removes_host_successfully(self, mock_db, mock_get_sr, mock_get_awx):
        from app.tasks.awx import awx_decommission

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_sr.return_value = {
            "server_name": "test",
            "awx_host_id": "h-456",
        }

        mock_awx = MagicMock()
        mock_get_awx.return_value = mock_awx

        result = awx_decommission("sr-id")
        assert result["exit_code"] == 0
        mock_awx.remove_host.assert_called_once_with("h-456")
