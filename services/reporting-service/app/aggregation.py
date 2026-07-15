"""
Deterministic report aggregation.

Every number here comes from a plain SQL count/aggregate over the ledger and
related tables — no LLM involved. This is what ai-agent-service's
summarize_report endpoint receives and is only ever asked to *phrase*, never
to compute. The stats dict shape here is a contract with
ai-agent-service/app/deterministic.py::deterministic_report_narrative and
ai-agent-service/app/llm_client.py::summarize_report — keep the key names in
sync if either side changes.
"""
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy.orm import Session

from app import models


def compute_period_bounds(period_type: str, reference: datetime) -> Tuple[datetime, datetime]:
    """Returns (period_start, period_end) for the given period type, ending at `reference`."""
    from datetime import timedelta

    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    day_start = reference.replace(hour=0, minute=0, second=0, microsecond=0)

    if period_type == "DAILY":
        return day_start, day_start + timedelta(hours=23, minutes=59, seconds=59)

    if period_type == "WEEKLY":
        week_start = day_start - timedelta(days=day_start.weekday())  # Monday of this week
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return week_start, week_end

    if period_type == "MONTHLY":
        month_start = day_start.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        month_end = next_month - timedelta(seconds=1)
        return month_start, month_end

    # ADHOC — default to "since start of today" through now
    return day_start, reference


def aggregate_stats(db: Session, period_start: datetime, period_end: datetime) -> dict:
    events_q = db.query(models.AttendanceEvent).filter(
        models.AttendanceEvent.event_ts >= period_start,
        models.AttendanceEvent.event_ts <= period_end,
    )

    total_checkins = events_q.filter(models.AttendanceEvent.event_type == "CHECK_IN").count()
    unique_employees = (
        db.query(models.AttendanceEvent.employee_id)
        .filter(
            models.AttendanceEvent.event_ts >= period_start,
            models.AttendanceEvent.event_ts <= period_end,
        )
        .distinct()
        .count()
    )
    flagged_count = events_q.filter(models.AttendanceEvent.status == "FLAGGED").count()

    open_anomaly_count = (
        db.query(models.AnomalyFlag)
        .filter(
            models.AnomalyFlag.created_at >= period_start,
            models.AnomalyFlag.created_at <= period_end,
            models.AnomalyFlag.status == "OPEN",
        )
        .count()
    )

    reg_q = db.query(models.RegularizationRequest).filter(
        models.RegularizationRequest.created_at >= period_start,
        models.RegularizationRequest.created_at <= period_end,
    )
    regularizations_submitted = reg_q.count()
    regularizations_approved = reg_q.filter(models.RegularizationRequest.status == "APPROVED").count()
    regularizations_rejected = reg_q.filter(models.RegularizationRequest.status == "REJECTED").count()

    return {
        "total_checkins": total_checkins,
        "unique_employees": unique_employees,
        "flagged_count": flagged_count,
        "open_anomaly_count": open_anomaly_count,
        "regularizations_submitted": regularizations_submitted,
        "regularizations_approved": regularizations_approved,
        "regularizations_rejected": regularizations_rejected,
    }
