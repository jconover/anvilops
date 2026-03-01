"""Unit tests for app.api.v1.compliance — helper functions.

Tests the pure/isolated functions without requiring a database.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.compliance import _get_puppet_service

# ---------------------------------------------------------------------------
# _get_puppet_service
# ---------------------------------------------------------------------------


class TestGetPuppetService:
    @patch.dict("sys.modules", {"app.services.puppet": None})
    def test_raises_503_when_module_not_importable(self):
        """When the puppet module can't be imported, return 503."""
        with pytest.raises(HTTPException) as exc_info:
            _get_puppet_service()
        assert exc_info.value.status_code == 503
        assert "not available" in exc_info.value.detail

    @patch("app.api.v1.compliance.logger")
    def test_raises_503_when_instantiation_fails(self, _mock_logger):
        """When the puppet service constructor throws, return 503."""
        mock_module = MagicMock()
        mock_module.PuppetEnterpriseServiceSync.side_effect = RuntimeError("bad config")

        with patch.dict("sys.modules", {"app.services.puppet": mock_module}):
            with pytest.raises(HTTPException) as exc_info:
                _get_puppet_service()
            assert exc_info.value.status_code == 503
            assert "could not be initialised" in exc_info.value.detail

    def test_returns_service_on_success(self):
        """Happy path: module is importable and constructor succeeds."""
        mock_module = MagicMock()
        mock_instance = MagicMock()
        mock_module.PuppetEnterpriseServiceSync.return_value = mock_instance

        with patch.dict("sys.modules", {"app.services.puppet": mock_module}):
            result = _get_puppet_service()
            assert result is mock_instance
