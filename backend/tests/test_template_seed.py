"""Unit tests for template_seed.seed_default_templates.

Uses AsyncMock to avoid any real database connections.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.template_seed import DEFAULT_TEMPLATES, seed_default_templates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(existing_names: set[str] | None = None):
    """Return a mock AsyncSession pre-configured with query results."""
    if existing_names is None:
        existing_names = set()

    session = AsyncMock()

    # Simulate session.execute(...) returning a result whose .all() gives rows
    result_mock = MagicMock()
    result_mock.all.return_value = [(name,) for name in existing_names]
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock()

    return session


# ---------------------------------------------------------------------------
# Happy-path seeding
# ---------------------------------------------------------------------------


class TestSeedDefaultTemplates:
    @pytest.mark.asyncio
    async def test_seeds_all_templates_when_db_is_empty(self):
        session = _make_session(existing_names=set())
        await seed_default_templates(session)
        # session.add should be called once per default template
        assert session.add.call_count == len(DEFAULT_TEMPLATES)

    @pytest.mark.asyncio
    async def test_flush_called_when_templates_inserted(self):
        session = _make_session(existing_names=set())
        await seed_default_templates(session)
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_existing_templates(self):
        # Pre-seed two templates
        existing = {DEFAULT_TEMPLATES[0]["name"], DEFAULT_TEMPLATES[1]["name"]}
        session = _make_session(existing_names=existing)
        await seed_default_templates(session)
        expected_adds = len(DEFAULT_TEMPLATES) - len(existing)
        assert session.add.call_count == expected_adds

    @pytest.mark.asyncio
    async def test_no_add_when_all_templates_exist(self):
        existing = {t["name"] for t in DEFAULT_TEMPLATES}
        session = _make_session(existing_names=existing)
        await seed_default_templates(session)
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_not_called_when_nothing_inserted(self):
        existing = {t["name"] for t in DEFAULT_TEMPLATES}
        session = _make_session(existing_names=existing)
        await seed_default_templates(session)
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_seed_inserts_correct_subset(self):
        # Only first three templates already exist
        existing = {DEFAULT_TEMPLATES[i]["name"] for i in range(3)}
        session = _make_session(existing_names=existing)
        await seed_default_templates(session)
        assert session.add.call_count == len(DEFAULT_TEMPLATES) - 3

    @pytest.mark.asyncio
    async def test_added_objects_are_server_template_instances(self):
        from app.models.template import ServerTemplate

        session = _make_session(existing_names=set())
        await seed_default_templates(session)
        for c in session.add.call_args_list:
            obj = c[0][0]
            assert isinstance(obj, ServerTemplate)

    @pytest.mark.asyncio
    async def test_added_templates_have_uuid_ids(self):
        session = _make_session(existing_names=set())
        await seed_default_templates(session)
        for c in session.add.call_args_list:
            obj = c[0][0]
            assert isinstance(obj.id, uuid.UUID)


# ---------------------------------------------------------------------------
# DEFAULT_TEMPLATES content validation
# ---------------------------------------------------------------------------


class TestDefaultTemplatesData:
    def test_six_default_templates_defined(self):
        assert len(DEFAULT_TEMPLATES) == 6

    def test_all_templates_have_required_keys(self):
        required = {"name", "os_type", "instance_size", "region", "puppet_role"}
        for t in DEFAULT_TEMPLATES:
            missing = required - t.keys()
            assert not missing, f"Template '{t['name']}' missing keys: {missing}"

    def test_template_names_are_unique(self):
        names = [t["name"] for t in DEFAULT_TEMPLATES]
        assert len(names) == len(set(names))

    def test_sort_orders_are_unique(self):
        orders = [t.get("sort_order") for t in DEFAULT_TEMPLATES if "sort_order" in t]
        assert len(orders) == len(set(orders))

    def test_windows_templates_have_domain_join(self):
        for t in DEFAULT_TEMPLATES:
            if "windows" in t["os_type"]:
                # SQL Server and .NET server are domain-joined; dev workstation is not
                # Just assert the key exists
                assert "domain_join" in t

    def test_sql_server_template_has_additional_storage(self):
        sql = next(t for t in DEFAULT_TEMPLATES if t["name"] == "SQL Server")
        assert len(sql["additional_storage"]) == 3

    def test_all_regions_are_us_east_1(self):
        for t in DEFAULT_TEMPLATES:
            assert t["region"] == "us-east-1"

    def test_instance_sizes_are_valid(self):
        valid = {"small", "medium", "large", "xl"}
        for t in DEFAULT_TEMPLATES:
            assert t["instance_size"] in valid, (
                f"Template '{t['name']}' has invalid instance_size '{t['instance_size']}'"
            )
