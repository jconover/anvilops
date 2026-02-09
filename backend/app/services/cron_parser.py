"""Simple cron expression utilities for AnvilOps scheduled builds.

Implements parsing, validation, next-run-time calculation, and
human-readable descriptions for standard 5-field cron expressions:

    minute  hour  day-of-month  month  day-of-week
    (0-59)  (0-23)  (1-31)      (1-12)  (0-6, 0=Sunday)

Supported syntax per field:
- ``*``           — any value
- ``5``           — exact value
- ``1,3,5``       — list of values
- ``1-5``         — range
- ``*/15``        — step (every 15)
- ``1-30/5``      — range with step

Day-of-week accepts 0-7 where both 0 and 7 map to Sunday.

No external dependencies -- this is a self-contained, lightweight
implementation suitable for the demo/prototype stage.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Common presets
# ---------------------------------------------------------------------------

CRON_PRESETS: dict[str, str] = {
    "daily_2am": "0 2 * * *",
    "weekly_monday": "0 2 * * 1",
    "weekdays_6am": "0 6 * * 1-5",
    "monthly_1st": "0 2 1 * *",
    "every_6_hours": "0 */6 * * *",
    "hourly": "0 * * * *",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FIELD_NAMES = ("minute", "hour", "day_of_month", "month", "day_of_week")

_FIELD_RANGES: dict[str, tuple[int, int]] = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day_of_month": (1, 31),
    "month": (1, 12),
    "day_of_week": (0, 6),
}

_DAY_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3,
    "thu": 4, "fri": 5, "sat": 6,
}

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class CronField(NamedTuple):
    """Parsed representation of a single cron field."""

    values: set[int]


def _replace_names(token: str, field_name: str) -> str:
    """Replace day/month name abbreviations with their numeric equivalents."""
    lower = token.lower()
    if field_name == "day_of_week":
        for name, num in _DAY_NAMES.items():
            lower = lower.replace(name, str(num))
    elif field_name == "month":
        for name, num in _MONTH_NAMES.items():
            lower = lower.replace(name, str(num))
    return lower


def _parse_field(token: str, field_name: str) -> CronField:
    """Parse a single cron field token into a set of allowed integer values."""
    lo, hi = _FIELD_RANGES[field_name]
    token = _replace_names(token, field_name)

    values: set[int] = set()

    for part in token.split(","):
        part = part.strip()
        if not part:
            continue

        # Handle step: */N or range/N
        step = 1
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)
            if step < 1:
                raise ValueError(f"Invalid step value: {step}")

        if part == "*":
            values.update(range(lo, hi + 1, step))
        elif "-" in part:
            range_lo, range_hi = part.split("-", 1)
            range_lo_int = int(range_lo)
            range_hi_int = int(range_hi)
            if range_lo_int < lo or range_hi_int > hi or range_lo_int > range_hi_int:
                raise ValueError(
                    f"Invalid range {range_lo_int}-{range_hi_int} "
                    f"for {field_name} (allowed {lo}-{hi})"
                )
            values.update(range(range_lo_int, range_hi_int + 1, step))
        else:
            val = int(part)
            # Normalize day_of_week 7 -> 0 (both mean Sunday)
            if field_name == "day_of_week" and val == 7:
                val = 0
            if val < lo or val > hi:
                raise ValueError(
                    f"Value {val} out of range for {field_name} (allowed {lo}-{hi})"
                )
            if step > 1:
                values.update(range(val, hi + 1, step))
            else:
                values.add(val)

    if not values:
        raise ValueError(f"No valid values for field {field_name}")

    return CronField(values=values)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_cron(expression: str) -> dict[str, set[int]]:
    """Parse a 5-field cron expression into its component value sets.

    Returns a dict mapping field names (minute, hour, day_of_month,
    month, day_of_week) to their set of allowed integer values.

    Raises ``ValueError`` on invalid expressions.
    """
    tokens = expression.strip().split()
    if len(tokens) != 5:
        raise ValueError(
            f"Expected 5 fields in cron expression, got {len(tokens)}: {expression!r}"
        )

    result: dict[str, set[int]] = {}
    for token, field_name in zip(tokens, _FIELD_NAMES):
        result[field_name] = _parse_field(token, field_name).values

    return result


def validate_cron(expression: str) -> bool:
    """Return ``True`` if the expression is a valid 5-field cron string."""
    try:
        parse_cron(expression)
        return True
    except (ValueError, TypeError):
        return False


def get_next_run(
    expression: str,
    after: datetime,
    timezone: str = "UTC",
) -> datetime:
    """Calculate the next execution time for a cron expression.

    Parameters
    ----------
    expression:
        A valid 5-field cron expression.
    after:
        The reference point -- the next run must be strictly after this
        time.
    timezone:
        IANA timezone string used to interpret the cron expression.
        The returned datetime is timezone-aware in the target timezone.

    Returns a timezone-aware ``datetime`` in the specified timezone.

    Raises ``ValueError`` if no valid next run can be found within
    ~4 years (to guard against impossible expressions).
    """
    fields = parse_cron(expression)
    tz = ZoneInfo(timezone)

    # Work in the target timezone
    if after.tzinfo is None:
        current = after.replace(tzinfo=tz)
    else:
        current = after.astimezone(tz)

    # Start from the next minute boundary
    current = current.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Safety limit: don't search more than ~4 years ahead
    max_iterations = 525_960  # 365.25 * 24 * 60 * 4 (4 years of minutes)

    for _ in range(max_iterations):
        matches_month = current.month in fields["month"]
        matches_dom = current.day in fields["day_of_month"]
        matches_dow = _weekday_to_cron(current.weekday()) in fields["day_of_week"]
        matches_hour = current.hour in fields["hour"]
        matches_minute = current.minute in fields["minute"]

        if matches_month and matches_dom and matches_dow and matches_hour and matches_minute:
            return current

        # Advance smartly: skip ahead when possible to avoid minute-by-minute crawl
        if not matches_month:
            # Jump to the first day of the next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1, hour=0, minute=0)
            else:
                current = current.replace(month=current.month + 1, day=1, hour=0, minute=0)
            continue

        if not matches_dom or not matches_dow:
            # Jump to the next day
            current = (current + timedelta(days=1)).replace(hour=0, minute=0)
            continue

        if not matches_hour:
            # Jump to the next hour
            current = (current + timedelta(hours=1)).replace(minute=0)
            continue

        # Only minute doesn't match -- advance by one minute
        current += timedelta(minutes=1)

    raise ValueError(
        f"Could not find next run time for {expression!r} "
        f"within 4 years of {after.isoformat()}"
    )


def _weekday_to_cron(weekday: int) -> int:
    """Convert Python weekday (0=Monday) to cron day-of-week (0=Sunday)."""
    return (weekday + 1) % 7


def describe_cron(expression: str) -> str:
    """Return a human-readable description of a cron expression.

    Examples::

        "0 2 * * *"   -> "Every day at 2:00 AM"
        "0 2 * * 1"   -> "Every Monday at 2:00 AM"
        "30 9 1 * *"  -> "On day 1 of every month at 9:30 AM"
        "*/15 * * * *" -> "Every 15 minutes"
        "0 6 * * 1-5" -> "Every weekday (Mon-Fri) at 6:00 AM"

    Falls back to showing the raw expression for complex cases.
    """
    try:
        fields = parse_cron(expression)
    except ValueError:
        return f"Invalid cron: {expression}"

    minutes = sorted(fields["minute"])
    hours = sorted(fields["hour"])
    doms = sorted(fields["day_of_month"])
    months = sorted(fields["month"])
    dows = sorted(fields["day_of_week"])

    all_minutes = set(range(0, 60))
    all_hours = set(range(0, 24))
    all_doms = set(range(1, 32))
    all_months = set(range(1, 13))
    all_dows = set(range(0, 7))

    dow_names_full = [
        "Sunday", "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday",
    ]

    parts: list[str] = []

    # --- Frequency description ---

    # Every N minutes
    if fields["hour"] == all_hours and fields["minute"] != all_minutes:
        tokens = expression.strip().split()
        if re.match(r"^\*/(\d+)$", tokens[0]):
            step = int(tokens[0].split("/")[1])
            parts.append(f"Every {step} minutes")
        elif len(minutes) == 1:
            pass  # handled below as specific time
        else:
            parts.append(f"At minutes {', '.join(str(m) for m in minutes)}")

    # Every N hours
    if fields["minute"] == {0} and fields["hour"] != all_hours:
        tokens = expression.strip().split()
        if re.match(r"^\*/(\d+)$", tokens[1]):
            step = int(tokens[1].split("/")[1])
            if not parts:
                parts.append(f"Every {step} hours")

    # Specific time
    if len(minutes) == 1 and len(hours) == 1 and not parts:
        h = hours[0]
        m = minutes[0]
        ampm = "AM" if h < 12 else "PM"
        display_h = h if h <= 12 else h - 12
        if display_h == 0:
            display_h = 12
        time_str = f"{display_h}:{m:02d} {ampm}"

        # Day-of-week specifics
        if fields["day_of_week"] == all_dows and fields["day_of_month"] == all_doms:
            if fields["month"] == all_months:
                parts.append(f"Every day at {time_str}")
            else:
                month_names = [
                    ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m_]
                    for m_ in months
                ]
                parts.append(f"In {', '.join(month_names)} at {time_str}")
        elif dows == [1, 2, 3, 4, 5]:
            parts.append(f"Every weekday (Mon-Fri) at {time_str}")
        elif dows == [0, 6]:
            parts.append(f"Every weekend (Sat-Sun) at {time_str}")
        elif len(dows) == 1:
            parts.append(f"Every {dow_names_full[dows[0]]} at {time_str}")
        elif len(dows) > 1:
            day_list = ", ".join(dow_names_full[d] for d in dows)
            parts.append(f"Every {day_list} at {time_str}")
        elif fields["day_of_month"] != all_doms:
            if len(doms) == 1:
                parts.append(f"On day {doms[0]} of every month at {time_str}")
            else:
                dom_list = ", ".join(str(d) for d in doms)
                parts.append(f"On days {dom_list} of every month at {time_str}")

    if not parts:
        return f"Cron: {expression}"

    return parts[0]
