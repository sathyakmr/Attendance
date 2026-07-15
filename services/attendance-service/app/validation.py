"""
Deterministic validation rules for incoming attendance events.

These rules run BEFORE any AI/anomaly-detection step and are what the design
doc (Section 6/9.3) calls the "deterministic fallback" — the system keeps
producing a correct, auditable ledger even if the AI agent is completely
unavailable. The AI anomaly engine (built in a later phase) consumes
VALIDATED/FLAGGED events downstream via the event bus; it never gates this
write path.
"""
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings


class ValidationResult:
    def __init__(self, status: models.EventStatus, notes: Optional[str] = None):
        self.status = status
        self.notes = notes


def haversine_distance_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def check_debounce(db: Session, employee_id, event_ts: datetime, event_type: str) -> Optional[str]:
    """
    Return a rejection reason if a near-duplicate punch of the SAME type
    exists, else None.

    Filtering by event_type matters: without it, a legitimate CHECK_OUT
    shortly after a CHECK_IN (or vice versa — perfectly normal for a short
    shift, a quick task, or just testing the system) would be wrongly
    rejected as a "duplicate punch" of the check-in. Debounce should only
    catch accidental double-taps of the *same* action, e.g. two CHECK_INs
    seconds apart, not a real state transition.
    """
    window_start = event_ts - timedelta(seconds=settings.debounce_seconds)
    recent = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.employee_id == employee_id,
            models.AttendanceEvent.event_type == event_type,
            models.AttendanceEvent.event_ts >= window_start,
            models.AttendanceEvent.event_ts <= event_ts,
            models.AttendanceEvent.status != models.EventStatus.REJECTED,
        )
        .order_by(models.AttendanceEvent.event_ts.desc())
        .first()
    )
    if recent:
        delta = (event_ts - recent.event_ts).total_seconds()
        return f"Duplicate {event_type} suppressed: prior {event_type} event {recent.id} only {int(delta)}s earlier"
    return None


def check_shift_window(employee: models.Employee, event_type: str, event_ts: datetime) -> Optional[str]:
    """Soft check — returns a flag note if outside the expected window, never blocks the write."""
    local_time = event_ts.timetz()
    if event_type == "CHECK_IN":
        earliest_allowed = (
            datetime.combine(event_ts.date(), employee.shift_start)
            - timedelta(minutes=settings.early_checkin_grace_minutes)
        ).time()
        shift_start_plus_grace = (
            datetime.combine(event_ts.date(), employee.shift_start)
            + timedelta(minutes=employee.grace_minutes)
        ).time()
        if local_time.replace(tzinfo=None) > shift_start_plus_grace:
            return f"Late check-in: after shift start {employee.shift_start} + {employee.grace_minutes}m grace"
    elif event_type == "CHECK_OUT":
        latest_allowed = (
            datetime.combine(event_ts.date(), employee.shift_end)
            + timedelta(minutes=settings.late_checkout_grace_minutes)
        ).time()
        if local_time.replace(tzinfo=None) > latest_allowed:
            return "Unusually late check-out — outside normal grace window"
    return None


def check_geofence(employee: models.Employee, latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    if not settings.enforce_geofence:
        return None
    if employee.geofence_lat is None or latitude is None or longitude is None:
        return None
    distance = haversine_distance_m(employee.geofence_lat, employee.geofence_lng, latitude, longitude)
    if distance > (employee.geofence_radius_m or 200):
        return f"Outside geofence: {int(distance)}m from assigned location"
    return None


def validate_event(
    db: Session,
    employee: models.Employee,
    event_type: str,
    event_ts: datetime,
    latitude: Optional[float],
    longitude: Optional[float],
) -> ValidationResult:
    if event_ts.tzinfo is None:
        event_ts = event_ts.replace(tzinfo=timezone.utc)

    dup_reason = check_debounce(db, employee.id, event_ts, event_type)
    if dup_reason:
        return ValidationResult(models.EventStatus.REJECTED, dup_reason)

    notes = []
    geofence_note = check_geofence(employee, latitude, longitude)
    if geofence_note:
        notes.append(geofence_note)

    shift_note = check_shift_window(employee, event_type, event_ts)
    if shift_note:
        notes.append(shift_note)

    if notes:
        return ValidationResult(models.EventStatus.FLAGGED, "; ".join(notes))

    return ValidationResult(models.EventStatus.VALIDATED, None)