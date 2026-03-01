"""Unit tests for scaling task helper functions.

Tests _get_group_metrics (pure stub function) and verifies the
ScalingService.calculate_desired_count integration logic used by
check_scaling_triggers.
"""

import pytest

from app.services.scaling import ScalingService
from app.tasks.scaling import _get_group_metrics

# ---------------------------------------------------------------------------
# _get_group_metrics stub
# ---------------------------------------------------------------------------


class TestGetGroupMetrics:
    def test_returns_dict(self):
        result = _get_group_metrics("group-001")
        assert isinstance(result, dict)

    def test_has_avg_cpu_key(self):
        result = _get_group_metrics("group-001")
        assert "avg_cpu" in result

    def test_avg_cpu_is_50(self):
        """Stub always returns 50% CPU utilisation."""
        result = _get_group_metrics("group-001")
        assert result["avg_cpu"] == 50.0

    def test_consistent_across_different_group_ids(self):
        """Stub returns same value regardless of group ID."""
        r1 = _get_group_metrics("group-aaa")
        r2 = _get_group_metrics("group-bbb")
        assert r1["avg_cpu"] == r2["avg_cpu"]

    def test_avg_cpu_is_within_valid_range(self):
        result = _get_group_metrics("group-001")
        assert 0.0 <= result["avg_cpu"] <= 100.0


# ---------------------------------------------------------------------------
# ScalingService.calculate_desired_count — used by check_scaling_triggers
# ---------------------------------------------------------------------------


@pytest.fixture
def svc():
    return ScalingService()


class TestCalculateDesiredCount:
    def test_scale_up_when_cpu_above_threshold(self, svc):
        group = {
            "current_count": 2,
            "min_instances": 1,
            "max_instances": 10,
            "scale_up_threshold": 70.0,
            "scale_down_threshold": 30.0,
        }
        metrics = {"avg_cpu": 85.0}
        desired = svc.calculate_desired_count(group, metrics)
        assert desired > group["current_count"]

    def test_scale_down_when_cpu_below_threshold(self, svc):
        group = {
            "current_count": 5,
            "min_instances": 1,
            "max_instances": 10,
            "scale_up_threshold": 70.0,
            "scale_down_threshold": 30.0,
        }
        metrics = {"avg_cpu": 10.0}
        desired = svc.calculate_desired_count(group, metrics)
        assert desired < group["current_count"]

    def test_no_change_within_thresholds(self, svc):
        """avg_cpu=50 is within default thresholds so no change expected."""
        group = {
            "current_count": 3,
            "min_instances": 1,
            "max_instances": 10,
            "scale_up_threshold": 70.0,
            "scale_down_threshold": 30.0,
        }
        metrics = {"avg_cpu": 50.0}
        desired = svc.calculate_desired_count(group, metrics)
        assert desired == group["current_count"]

    def test_does_not_scale_below_min_instances(self, svc):
        group = {
            "current_count": 1,
            "min_instances": 1,
            "max_instances": 10,
            "scale_up_threshold": 70.0,
            "scale_down_threshold": 30.0,
        }
        metrics = {"avg_cpu": 5.0}
        desired = svc.calculate_desired_count(group, metrics)
        assert desired >= group["min_instances"]

    def test_does_not_scale_above_max_instances(self, svc):
        group = {
            "current_count": 10,
            "min_instances": 1,
            "max_instances": 10,
            "scale_up_threshold": 70.0,
            "scale_down_threshold": 30.0,
        }
        metrics = {"avg_cpu": 99.0}
        desired = svc.calculate_desired_count(group, metrics)
        assert desired <= group["max_instances"]
