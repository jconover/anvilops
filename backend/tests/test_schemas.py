"""Tests for Pydantic schema validation rules.

These are pure validation tests -- no database, Redis, or external APIs required.
Each test instantiates a schema and verifies it either accepts or rejects the input.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.scaling import ScalingGroupCreate
from app.schemas.schedule import ScheduleCreate
from app.schemas.server import ServerCreateRequest, StorageConfig
from app.schemas.template import TemplateCreate

# ---------------------------------------------------------------------------
# Helpers: minimal valid payloads
# ---------------------------------------------------------------------------

_VALID_SERVER = {
    "environment": "dev",
    "os_type": "ubuntu_2204",
    "instance_size": "medium",
    "vpc_id": "vpc-abc123",
    "subnet_id": "subnet-abc123",
}

_VALID_SCALING = {
    "name": "web-fleet",
    "environment": "dev",
    "os_type": "ubuntu_2204",
    "instance_size": "medium",
    "region": "us-east-1",
    "vpc_id": "vpc-abc123",
    "subnet_id": "subnet-abc123",
}

_VALID_SCHEDULE_ONE_TIME = {
    "name": "nightly-build",
    "schedule_type": "one_time",
    "scheduled_at": datetime.now(timezone.utc).isoformat(),
    "server_config": {"key": "value"},
}

_VALID_SCHEDULE_RECURRING = {
    "name": "cron-build",
    "schedule_type": "recurring",
    "cron_expression": "0 2 * * *",
    "server_config": {"key": "value"},
}


# ===================================================================
# ServerCreateRequest
# ===================================================================


class TestServerCreateRequest:
    """Validation rules for the server creation payload."""

    def test_server_create_valid(self):
        """A complete, valid payload is accepted without errors."""
        server = ServerCreateRequest(**_VALID_SERVER)
        assert server.environment == "dev"
        assert server.os_type == "ubuntu_2204"
        assert server.instance_size == "medium"
        assert server.vpc_id == "vpc-abc123"
        assert server.subnet_id == "subnet-abc123"

    def test_server_create_invalid_environment(self):
        """An environment value outside the allowed Literal raises ValidationError."""
        payload = {**_VALID_SERVER, "environment": "invalid"}
        with pytest.raises(ValidationError):
            ServerCreateRequest(**payload)

    def test_server_create_invalid_os_type(self):
        """An os_type value outside the allowed Literal raises ValidationError."""
        payload = {**_VALID_SERVER, "os_type": "centos"}
        with pytest.raises(ValidationError):
            ServerCreateRequest(**payload)

    def test_server_create_invalid_instance_size(self):
        """An instance_size value outside the allowed Literal raises ValidationError."""
        payload = {**_VALID_SERVER, "instance_size": "micro"}
        with pytest.raises(ValidationError):
            ServerCreateRequest(**payload)

    def test_server_create_missing_required(self):
        """Omitting a required field (vpc_id) raises ValidationError."""
        payload = {
            "environment": "dev",
            "os_type": "ubuntu_2204",
            "instance_size": "medium",
            "subnet_id": "subnet-abc123",
        }
        with pytest.raises(ValidationError):
            ServerCreateRequest(**payload)

    def test_server_create_defaults(self):
        """Default values are applied for optional fields."""
        server = ServerCreateRequest(**_VALID_SERVER)
        assert server.region == "us-east-1"
        assert server.security_profile == "internal_only"
        assert server.domain_join is False
        assert server.software_packages == []
        assert server.puppet_role == "base"
        assert server.additional_storage == []
        assert server.tags == {}


# ===================================================================
# StorageConfig
# ===================================================================


class TestStorageConfig:
    """Validation rules for the attached storage configuration."""

    def test_storage_valid(self):
        """A typical valid storage config is accepted."""
        storage = StorageConfig(size_gb=100, volume_type="gp3")
        assert storage.size_gb == 100
        assert storage.volume_type == "gp3"

    def test_storage_min_size(self):
        """The minimum allowed size (1 GB) is accepted."""
        storage = StorageConfig(size_gb=1)
        assert storage.size_gb == 1

    def test_storage_max_size(self):
        """The maximum allowed size (16384 GB) is accepted."""
        storage = StorageConfig(size_gb=16384)
        assert storage.size_gb == 16384

    def test_storage_below_min(self):
        """A size below the minimum (0) raises ValidationError."""
        with pytest.raises(ValidationError):
            StorageConfig(size_gb=0)

    def test_storage_above_max(self):
        """A size above the maximum (16385) raises ValidationError."""
        with pytest.raises(ValidationError):
            StorageConfig(size_gb=16385)

    def test_storage_invalid_type(self):
        """A volume_type outside the allowed Literal raises ValidationError."""
        with pytest.raises(ValidationError):
            StorageConfig(size_gb=100, volume_type="ssd")


# ===================================================================
# ScalingGroupCreate
# ===================================================================


class TestScalingGroupCreate:
    """Validation rules for the scaling group creation payload."""

    def test_scaling_valid(self):
        """A complete, valid payload is accepted and defaults are applied."""
        group = ScalingGroupCreate(**_VALID_SCALING)
        assert group.name == "web-fleet"
        assert group.min_instances == 1
        assert group.max_instances == 5
        assert group.desired_count == 1
        assert group.scale_up_threshold == 80
        assert group.scale_down_threshold == 20
        assert group.cooldown_seconds == 300

    def test_scaling_min_greater_than_max(self):
        """min_instances > max_instances raises ValidationError."""
        payload = {**_VALID_SCALING, "min_instances": 10, "max_instances": 5}
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)

    def test_scaling_desired_below_min(self):
        """desired_count < min_instances raises ValidationError."""
        payload = {**_VALID_SCALING, "min_instances": 3, "desired_count": 1}
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)

    def test_scaling_desired_above_max(self):
        """desired_count > max_instances raises ValidationError."""
        payload = {**_VALID_SCALING, "max_instances": 5, "desired_count": 10}
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)

    def test_scaling_threshold_invalid(self):
        """scale_down_threshold > scale_up_threshold raises ValidationError."""
        payload = {
            **_VALID_SCALING,
            "scale_down_threshold": 50,
            "scale_up_threshold": 50,
        }
        # scale_down_threshold must be strictly < scale_up_threshold,
        # but 50 is the upper bound for scale_down_threshold and lower
        # bound for scale_up_threshold, so equal values should still fail.
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)

    def test_scaling_threshold_equal(self):
        """Equal thresholds (both at boundary values) raise ValidationError."""
        payload = {
            **_VALID_SCALING,
            "scale_down_threshold": 50,
            "scale_up_threshold": 50,
        }
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)

    def test_scaling_instances_out_of_range(self):
        """min_instances below the ge=1 constraint raises ValidationError."""
        payload = {**_VALID_SCALING, "min_instances": 0}
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)

    def test_scaling_max_instances_limit(self):
        """max_instances above the le=20 constraint raises ValidationError."""
        payload = {**_VALID_SCALING, "max_instances": 21}
        with pytest.raises(ValidationError):
            ScalingGroupCreate(**payload)


# ===================================================================
# ScheduleCreate
# ===================================================================


class TestScheduleCreate:
    """Validation rules for the build schedule creation payload."""

    def test_schedule_one_time_valid(self):
        """A valid one_time schedule with scheduled_at is accepted."""
        schedule = ScheduleCreate(**_VALID_SCHEDULE_ONE_TIME)
        assert schedule.schedule_type == "one_time"
        assert schedule.scheduled_at is not None

    def test_schedule_one_time_missing_scheduled_at(self):
        """A one_time schedule without scheduled_at raises ValidationError."""
        payload = {
            "name": "nightly-build",
            "schedule_type": "one_time",
            "server_config": {"key": "value"},
        }
        with pytest.raises(ValidationError):
            ScheduleCreate(**payload)

    def test_schedule_recurring_valid(self):
        """A valid recurring schedule with cron_expression is accepted."""
        schedule = ScheduleCreate(**_VALID_SCHEDULE_RECURRING)
        assert schedule.schedule_type == "recurring"
        assert schedule.cron_expression == "0 2 * * *"

    def test_schedule_recurring_missing_cron(self):
        """A recurring schedule without cron_expression raises ValidationError."""
        payload = {
            "name": "cron-build",
            "schedule_type": "recurring",
            "server_config": {"key": "value"},
        }
        with pytest.raises(ValidationError):
            ScheduleCreate(**payload)


# ===================================================================
# TemplateCreate
# ===================================================================


class TestTemplateCreate:
    """Validation rules for the server template creation payload."""

    def test_template_valid(self):
        """A complete, valid template payload is accepted."""
        template = TemplateCreate(
            name="My Template",
            os_type="ubuntu_2204",
            instance_size="small",
        )
        assert template.name == "My Template"
        assert template.os_type == "ubuntu_2204"
        assert template.instance_size == "small"

    def test_template_empty_name(self):
        """An empty name (min_length=1) raises ValidationError."""
        with pytest.raises(ValidationError):
            TemplateCreate(name="", os_type="ubuntu_2204", instance_size="small")
