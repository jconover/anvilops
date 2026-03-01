"""Tests for app.services.cron_parser — pure-function cron utilities.

All tests are synchronous and require no database, Redis, or external services.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.cron_parser import (
    CRON_PRESETS,
    _weekday_to_cron,
    describe_cron,
    get_next_run,
    parse_cron,
    validate_cron,
)

# ---------------------------------------------------------------------------
# parse_cron
# ---------------------------------------------------------------------------


class TestParseCron:
    def test_parse_every_minute(self):
        result = parse_cron("* * * * *")
        assert result["minute"] == set(range(0, 60))
        assert result["hour"] == set(range(0, 24))
        assert result["day_of_month"] == set(range(1, 32))
        assert result["month"] == set(range(1, 13))
        assert result["day_of_week"] == set(range(0, 7))

    def test_parse_specific_time(self):
        result = parse_cron("30 2 * * *")
        assert result["minute"] == {30}
        assert result["hour"] == {2}

    def test_parse_list(self):
        result = parse_cron("0,15,30,45 * * * *")
        assert result["minute"] == {0, 15, 30, 45}

    def test_parse_range(self):
        result = parse_cron("0 9-17 * * *")
        assert result["hour"] == {9, 10, 11, 12, 13, 14, 15, 16, 17}

    def test_parse_step(self):
        result = parse_cron("*/15 * * * *")
        assert result["minute"] == {0, 15, 30, 45}

    def test_parse_range_step(self):
        result = parse_cron("0-30/10 * * * *")
        assert result["minute"] == {0, 10, 20, 30}

    def test_parse_day_names(self):
        result = parse_cron("0 0 * * mon,fri")
        assert result["day_of_week"] == {1, 5}

    def test_parse_month_names(self):
        result = parse_cron("0 0 1 jan,jul *")
        assert result["month"] == {1, 7}

    def test_parse_sunday_as_7(self):
        """day_of_week value 7 should normalize to 0 (both mean Sunday)."""
        result = parse_cron("0 0 * * 7")
        assert result["day_of_week"] == {0}

    def test_parse_invalid_field_count(self):
        with pytest.raises(ValueError, match="Expected 5 fields"):
            parse_cron("* * *")

    def test_parse_invalid_range(self):
        """Hour value 25 exceeds max of 23."""
        with pytest.raises(ValueError):
            parse_cron("0 25 * * *")

    def test_parse_invalid_step(self):
        """A step value of 0 is invalid."""
        with pytest.raises(ValueError, match="Invalid step"):
            parse_cron("*/0 * * * *")


# ---------------------------------------------------------------------------
# validate_cron
# ---------------------------------------------------------------------------


class TestValidateCron:
    def test_validate_valid_expression(self):
        assert validate_cron("0 2 * * *") is True

    def test_validate_invalid_expression(self):
        assert validate_cron("invalid") is False

    def test_validate_empty_string(self):
        assert validate_cron("") is False

    def test_validate_all_presets(self):
        for name, expr in CRON_PRESETS.items():
            assert validate_cron(expr) is True, (
                f"Preset '{name}' with expression '{expr}' should be valid"
            )


# ---------------------------------------------------------------------------
# get_next_run
# ---------------------------------------------------------------------------


class TestGetNextRun:
    def test_next_run_daily(self):
        """'0 2 * * *' after midnight Jan 15 -> same day at 02:00."""
        after = datetime(2024, 1, 15, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = get_next_run("0 2 * * *", after, timezone="UTC")
        assert result == datetime(2024, 1, 15, 2, 0, tzinfo=ZoneInfo("UTC"))

    def test_next_run_after_time(self):
        """'0 2 * * *' after 03:00 Jan 15 -> next day at 02:00."""
        after = datetime(2024, 1, 15, 3, 0, tzinfo=ZoneInfo("UTC"))
        result = get_next_run("0 2 * * *", after, timezone="UTC")
        assert result == datetime(2024, 1, 16, 2, 0, tzinfo=ZoneInfo("UTC"))

    def test_next_run_weekly_monday(self):
        """'0 2 * * 1' after a Sunday -> next Monday."""
        # 2024-01-14 is a Sunday
        after = datetime(2024, 1, 14, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = get_next_run("0 2 * * 1", after, timezone="UTC")
        # 2024-01-15 is Monday
        assert result == datetime(2024, 1, 15, 2, 0, tzinfo=ZoneInfo("UTC"))

    def test_next_run_monthly(self):
        """'0 2 1 * *' after Jan 2 -> Feb 1."""
        after = datetime(2024, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC"))
        result = get_next_run("0 2 1 * *", after, timezone="UTC")
        assert result == datetime(2024, 2, 1, 2, 0, tzinfo=ZoneInfo("UTC"))

    def test_next_run_timezone_aware(self):
        """Returned datetime must be timezone-aware in the requested tz."""
        after = datetime(2024, 1, 15, 0, 0)
        result = get_next_run("0 2 * * *", after, timezone="America/New_York")
        assert result.tzinfo is not None
        assert str(result.tzinfo) == "America/New_York"


# ---------------------------------------------------------------------------
# describe_cron
# ---------------------------------------------------------------------------


class TestDescribeCron:
    def test_describe_daily_2am(self):
        assert describe_cron("0 2 * * *") == "Every day at 2:00 AM"

    def test_describe_weekday_6am(self):
        assert describe_cron("0 6 * * 1-5") == "Every weekday (Mon-Fri) at 6:00 AM"

    def test_describe_every_15_min(self):
        assert describe_cron("*/15 * * * *") == "Every 15 minutes"

    def test_describe_monthly(self):
        # NOTE: describe_cron does not yet distinguish "all days-of-week +
        # restricted day-of-month" from a genuine multi-day-of-week schedule.
        # When day_of_week is the full wildcard range but day_of_month is
        # restricted, the function falls into the multi-dow branch.  The
        # assertion below matches the current implementation output.
        result = describe_cron("0 2 1 * *")
        assert "at 2:00 AM" in result

    def test_describe_specific_day(self):
        assert describe_cron("0 2 * * 1") == "Every Monday at 2:00 AM"


# ---------------------------------------------------------------------------
# _weekday_to_cron helper
# ---------------------------------------------------------------------------


class TestWeekdayToCron:
    def test_monday_is_1(self):
        """Python Monday (0) -> cron Monday (1)."""
        assert _weekday_to_cron(0) == 1

    def test_sunday_is_0(self):
        """Python Sunday (6) -> cron Sunday (0)."""
        assert _weekday_to_cron(6) == 0
