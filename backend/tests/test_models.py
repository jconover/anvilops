"""Tests for SQLAlchemy model definitions (app.models).

These tests validate model metadata, table names, column presence,
and __repr__ methods without requiring a live database connection.
Models are imported and inspected via SQLAlchemy's mapper introspection.
"""

import uuid
from datetime import datetime, timezone

from app.db.base import Base
from app.models.audit import AuditLog
from app.models.drift import DriftAlert, DriftEvent
from app.models.notification import Notification
from app.models.scaling import ScalingGroup, ScalingGroupMember
from app.models.schedule import BuildSchedule, ScheduleExecution
from app.models.server import BuildStep, ServerRequest
from app.models.template import ServerTemplate

# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class TestBase:
    """Verify common columns on the abstract Base class."""

    def test_base_is_abstract(self):
        assert Base.__abstract__ is True

    def test_base_has_id_column(self):
        # All concrete models inherit id from Base
        mapper = ServerRequest.__mapper__
        assert "id" in mapper.columns.keys()

    def test_base_has_created_at_column(self):
        mapper = ServerRequest.__mapper__
        assert "created_at" in mapper.columns.keys()

    def test_base_has_updated_at_column(self):
        mapper = ServerRequest.__mapper__
        assert "updated_at" in mapper.columns.keys()


# ---------------------------------------------------------------------------
# ServerRequest
# ---------------------------------------------------------------------------


class TestServerRequestModel:
    def test_tablename(self):
        assert ServerRequest.__tablename__ == "server_requests"

    def test_required_columns_present(self):
        cols = set(ServerRequest.__mapper__.columns.keys())
        expected = {
            "id", "server_name", "environment", "os_type", "instance_size",
            "region", "vpc_id", "subnet_id", "security_profile", "domain_join",
            "software_packages", "additional_storage", "tags", "puppet_role",
            "status", "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_optional_columns_present(self):
        cols = set(ServerRequest.__mapper__.columns.keys())
        optional = {
            "template_id", "status_message", "aws_instance_id",
            "private_ip", "public_ip", "dns_name",
            "terraform_workspace", "terraform_state_key",
            "awx_host_id", "awx_inventory_id", "awx_job_ids",
            "puppet_certname", "puppet_node_group_id",
            "puppet_last_report_status", "puppet_enrolled_at",
            "cmdb_sys_id",
        }
        assert optional.issubset(cols)

    def test_repr(self):
        test_id = uuid.uuid4()
        sr = ServerRequest(
            id=test_id,
            server_name="TEST-WEB-01",
            environment="dev",
            os_type="ubuntu_2204",
            instance_size="medium",
            region="us-east-1",
            vpc_id="vpc-abc",
            subnet_id="subnet-abc",
            status="pending",
        )
        r = repr(sr)
        assert "ServerRequest" in r
        assert "TEST-WEB-01" in r
        assert "dev" in r
        assert "pending" in r

    def test_build_steps_relationship_exists(self):
        rels = ServerRequest.__mapper__.relationships.keys()
        assert "build_steps" in rels


# ---------------------------------------------------------------------------
# BuildStep
# ---------------------------------------------------------------------------


class TestBuildStepModel:
    def test_tablename(self):
        assert BuildStep.__tablename__ == "build_steps"

    def test_columns_present(self):
        cols = set(BuildStep.__mapper__.columns.keys())
        expected = {
            "id", "server_request_id", "step_name", "step_order",
            "status", "started_at", "completed_at", "output_log",
            "error_message", "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        bs = BuildStep(
            id=uuid.uuid4(),
            server_request_id=uuid.uuid4(),
            step_name="terraform_apply",
            step_order=2,
            status="completed",
        )
        r = repr(bs)
        assert "BuildStep" in r
        assert "terraform_apply" in r


# ---------------------------------------------------------------------------
# ServerTemplate
# ---------------------------------------------------------------------------


class TestServerTemplateModel:
    def test_tablename(self):
        assert ServerTemplate.__tablename__ == "server_templates"

    def test_columns_present(self):
        cols = set(ServerTemplate.__mapper__.columns.keys())
        expected = {
            "id", "name", "description", "icon", "is_active", "sort_order",
            "os_type", "instance_size", "region", "security_profile",
            "puppet_role", "domain_join", "software_packages",
            "additional_storage", "default_tags",
            "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        t = ServerTemplate(
            id=uuid.uuid4(),
            name="Web Server",
            os_type="ubuntu_2204",
            instance_size="medium",
            is_active=True,
        )
        r = repr(t)
        assert "ServerTemplate" in r
        assert "Web Server" in r


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class TestAuditLogModel:
    def test_tablename(self):
        assert AuditLog.__tablename__ == "audit_logs"

    def test_columns_present(self):
        cols = set(AuditLog.__mapper__.columns.keys())
        expected = {
            "id", "timestamp", "action", "category",
            "actor_email", "actor_role",
            "resource_type", "resource_id", "resource_name",
            "details", "ip_address", "user_agent",
            "status", "error_message",
            "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        al = AuditLog(
            id=uuid.uuid4(),
            action="server.created",
            category="server",
            actor_email="user@example.com",
            resource_id="abc-123",
            status="success",
        )
        r = repr(al)
        assert "AuditLog" in r
        assert "server.created" in r


# ---------------------------------------------------------------------------
# DriftEvent / DriftAlert
# ---------------------------------------------------------------------------


class TestDriftEventModel:
    def test_tablename(self):
        assert DriftEvent.__tablename__ == "drift_events"

    def test_columns_present(self):
        cols = set(DriftEvent.__mapper__.columns.keys())
        expected = {
            "id", "server_request_id", "certname", "detected_at",
            "resource_type", "resource_title", "property_name",
            "severity", "is_corrective", "is_resolved",
            "drift_category", "report_hash",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        de = DriftEvent(
            id=uuid.uuid4(),
            server_request_id=uuid.uuid4(),
            certname="web01.anvilops.internal",
            detected_at=datetime.now(timezone.utc),
            resource_type="File",
            resource_title="/etc/nginx/nginx.conf",
            property_name="content",
            severity="high",
            is_resolved=False,
        )
        r = repr(de)
        assert "DriftEvent" in r
        assert "web01.anvilops.internal" in r

    def test_alerts_relationship_exists(self):
        rels = DriftEvent.__mapper__.relationships.keys()
        assert "alerts" in rels


class TestDriftAlertModel:
    def test_tablename(self):
        assert DriftAlert.__tablename__ == "drift_alerts"

    def test_columns_present(self):
        cols = set(DriftAlert.__mapper__.columns.keys())
        expected = {
            "id", "drift_event_id", "server_request_id",
            "alert_type", "severity", "title", "message",
            "is_acknowledged", "acknowledged_by", "acknowledged_at",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        da = DriftAlert(
            id=uuid.uuid4(),
            alert_type="repeated_drift",
            severity="high",
            title="Repeated drift detected",
            message="File drift detected 3 times",
            is_acknowledged=False,
        )
        r = repr(da)
        assert "DriftAlert" in r
        assert "repeated_drift" in r


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


class TestNotificationModel:
    def test_tablename(self):
        assert Notification.__tablename__ == "notifications"

    def test_columns_present(self):
        cols = set(Notification.__mapper__.columns.keys())
        expected = {
            "id", "user_email", "title", "message",
            "category", "severity", "is_read", "read_at",
            "resource_type", "resource_id", "action_url",
            "icon", "details",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        n = Notification(
            id=uuid.uuid4(),
            user_email="admin@corp.com",
            title="Build completed",
            message="Server build finished successfully",
            category="build",
            is_read=False,
        )
        r = repr(n)
        assert "Notification" in r
        assert "admin@corp.com" in r


# ---------------------------------------------------------------------------
# ScalingGroup / ScalingGroupMember
# ---------------------------------------------------------------------------


class TestScalingGroupModel:
    def test_tablename(self):
        assert ScalingGroup.__tablename__ == "scaling_groups"

    def test_columns_present(self):
        cols = set(ScalingGroup.__mapper__.columns.keys())
        expected = {
            "id", "name", "description", "status",
            "environment", "os_type", "instance_size", "region",
            "vpc_id", "subnet_id", "security_profile", "puppet_role",
            "min_instances", "max_instances", "desired_count", "current_count",
            "scale_up_threshold", "scale_down_threshold", "cooldown_seconds",
            "last_scaled_at",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        sg = ScalingGroup(
            id=uuid.uuid4(),
            name="web-fleet",
            environment="dev",
            os_type="ubuntu_2204",
            instance_size="medium",
            region="us-east-1",
            vpc_id="vpc-abc",
            subnet_id="subnet-abc",
            status="active",
            current_count=3,
        )
        r = repr(sg)
        assert "ScalingGroup" in r
        assert "web-fleet" in r

    def test_members_relationship_exists(self):
        rels = ScalingGroup.__mapper__.relationships.keys()
        assert "members" in rels


class TestScalingGroupMemberModel:
    def test_tablename(self):
        assert ScalingGroupMember.__tablename__ == "scaling_group_members"

    def test_columns_present(self):
        cols = set(ScalingGroupMember.__mapper__.columns.keys())
        expected = {
            "id", "scaling_group_id", "server_request_id",
            "member_index", "status",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        m = ScalingGroupMember(
            id=uuid.uuid4(),
            scaling_group_id=uuid.uuid4(),
            member_index=0,
            status="active",
        )
        r = repr(m)
        assert "ScalingGroupMember" in r


# ---------------------------------------------------------------------------
# BuildSchedule / ScheduleExecution
# ---------------------------------------------------------------------------


class TestBuildScheduleModel:
    def test_tablename(self):
        assert BuildSchedule.__tablename__ == "build_schedules"

    def test_columns_present(self):
        cols = set(BuildSchedule.__mapper__.columns.keys())
        expected = {
            "id", "name", "description", "status", "schedule_type",
            "scheduled_at", "cron_expression", "timezone",
            "next_run_at", "last_run_at", "server_config",
            "max_runs", "run_count", "created_by",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        bs = BuildSchedule(
            id=uuid.uuid4(),
            name="nightly-build",
            schedule_type="recurring",
            status="active",
            server_config={"key": "value"},
        )
        r = repr(bs)
        assert "BuildSchedule" in r
        assert "nightly-build" in r

    def test_executions_relationship_exists(self):
        rels = BuildSchedule.__mapper__.relationships.keys()
        assert "executions" in rels


class TestScheduleExecutionModel:
    def test_tablename(self):
        assert ScheduleExecution.__tablename__ == "schedule_executions"

    def test_columns_present(self):
        cols = set(ScheduleExecution.__mapper__.columns.keys())
        expected = {
            "id", "schedule_id", "server_request_id",
            "status", "scheduled_for", "started_at",
            "completed_at", "error_message",
        }
        assert expected.issubset(cols)

    def test_repr(self):
        se = ScheduleExecution(
            id=uuid.uuid4(),
            schedule_id=uuid.uuid4(),
            status="completed",
            scheduled_for=datetime.now(timezone.utc),
        )
        r = repr(se)
        assert "ScheduleExecution" in r
        assert "completed" in r


# ---------------------------------------------------------------------------
# models/__init__.py exports
# ---------------------------------------------------------------------------


class TestModelsInit:
    """Verify all models are exported from the models package."""

    def test_all_models_exported(self):
        from app.models import __all__

        expected = {
            "AuditLog", "ServerRequest", "BuildStep", "ServerTemplate",
            "Notification", "ScalingGroup", "ScalingGroupMember",
            "BuildSchedule", "ScheduleExecution", "DriftEvent", "DriftAlert",
        }
        assert expected == set(__all__)
