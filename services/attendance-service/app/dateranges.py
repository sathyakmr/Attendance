"""
Resolves the dashboard's date-range filter presets into concrete
(start, end) datetime bounds. Kept local to attendance-service rather than
shared with reporting-service's aggregation.py, since the two services are
independently deployable bounded contexts — duplicating ~15 lines of date
arithmetic is cheaper than introducing a cross-service dependency for it.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

VALID_PRESETS = {"TODAY", "YESTERDAY", "THIS_WEEK", "THIS_MONTH"}


def resolve_preset(preset: str, reference: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    if reference is None:
        reference = datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    day_start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    preset = preset.upper()

    if preset == "TODAY":
        return day_start, day_start + timedelta(hours=23, minutes=59, seconds=59)

    if preset == "YESTERDAY":
        y_start = day_start - timedelta(days=1)
        return y_start, y_start + timedelta(hours=23, minutes=59, seconds=59)

    if preset == "THIS_WEEK":
        week_start = day_start - timedelta(days=day_start.weekday())  # Monday
        return week_start, week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    if preset == "THIS_MONTH":
        month_start = day_start.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        return month_start, next_month - timedelta(seconds=1)

    raise ValueError(f"Unknown date preset: {preset}. Valid presets: {sorted(VALID_PRESETS)}")
