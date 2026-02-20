"""Unit tests for scaling helper functions.

All tests exercise pure in-memory logic -- no database, Redis,
or external API connections are required.
"""

import re

import pytest

from app.services.scaling import ScalingService, _generate_server_name


# ------------------------------------------------------------------
# _generate_server_name
# ------------------------------------------------------------------


class TestGenerateServerName:
    """Verify server name generation produces ENV-ROLE-RANDOM format."""

    def test_generate_name_production_web(self):
        """production + web_server must produce PROD-WEB-xxxx."""
        name = _generate_server_name("production", "web_server")
        assert name.startswith("PROD-WEB-")

    def test_generate_name_dev_base(self):
        """dev + base must produce DEV-SRV-xxxx."""
        name = _generate_server_name("dev", "base")
        assert name.startswith("DEV-SRV-")

    def test_generate_name_staging_db(self):
        """staging + db_server must produce STG-DB-xxxx."""
        name = _generate_server_name("staging", "db_server")
        assert name.startswith("STG-DB-")

    def test_generate_name_unknown_env(self):
        """Unknown environment defaults to SRV abbreviation."""
        name = _generate_server_name("unknown", "base")
        assert name.startswith("SRV-SRV-")

    def test_generate_name_suffix_length(self):
        """The random suffix after the last hyphen must be 4 hex characters."""
        name = _generate_server_name("production", "web_server")
        suffix = name.rsplit("-", 1)[1]
        assert len(suffix) == 4
        assert re.fullmatch(r"[0-9a-f]{4}", suffix) is not None

    def test_generate_name_unique(self):
        """Two consecutive calls must produce different names (random suffix)."""
        name1 = _generate_server_name("production", "web_server")
        name2 = _generate_server_name("production", "web_server")
        assert name1 != name2


# ------------------------------------------------------------------
# ScalingService.calculate_desired_count
# ------------------------------------------------------------------


class TestCalculateDesiredCount:
    """Verify the scaling decision logic based on CPU thresholds."""

    @pytest.fixture
    def service(self) -> ScalingService:
        return ScalingService()

    def _make_group(
        self,
        current: int = 3,
        min_inst: int = 1,
        max_inst: int = 5,
        up_thresh: int = 80,
        down_thresh: int = 20,
    ) -> dict:
        return {
            "current_count": current,
            "min_instances": min_inst,
            "max_instances": max_inst,
            "scale_up_threshold": up_thresh,
            "scale_down_threshold": down_thresh,
        }

    def test_scale_up(self, service: ScalingService):
        """CPU above scale_up_threshold with headroom should add one instance."""
        group = self._make_group(current=2, max_inst=5, up_thresh=80)
        result = service.calculate_desired_count(group, {"avg_cpu": 85.0})
        assert result == 3

    def test_scale_down(self, service: ScalingService):
        """CPU below scale_down_threshold with room should remove one instance."""
        group = self._make_group(current=3, min_inst=1, down_thresh=20)
        result = service.calculate_desired_count(group, {"avg_cpu": 15.0})
        assert result == 2

    def test_no_scale_in_range(self, service: ScalingService):
        """CPU between thresholds should keep current count unchanged."""
        group = self._make_group(current=3, up_thresh=80, down_thresh=20)
        result = service.calculate_desired_count(group, {"avg_cpu": 50.0})
        assert result == 3

    def test_scale_up_at_max(self, service: ScalingService):
        """Already at max_instances: scale up must not exceed max."""
        group = self._make_group(current=5, max_inst=5, up_thresh=80)
        result = service.calculate_desired_count(group, {"avg_cpu": 90.0})
        assert result == 5

    def test_scale_down_at_min(self, service: ScalingService):
        """Already at min_instances: scale down must not go below min."""
        group = self._make_group(current=1, min_inst=1, down_thresh=20)
        result = service.calculate_desired_count(group, {"avg_cpu": 10.0})
        assert result == 1

    def test_scale_up_respects_max(self, service: ScalingService):
        """One below max with high CPU should scale to exactly max."""
        group = self._make_group(current=4, max_inst=5, up_thresh=80)
        result = service.calculate_desired_count(group, {"avg_cpu": 90.0})
        assert result == 5
