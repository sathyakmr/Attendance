"""
Deterministic anomaly detection rules.

These run for every VALIDATED/FLAGGED attendance event and produce a
rule_score in [0, 1] plus structured `details`. This is the layer the design
doc calls out as the always-available fallback (Section 9.3): even with the
LLM completely disabled, the system still detects and routes anomalies
correctly — the LLM (see llm_client.explain_anomaly) only ever adds
human-readable narrative on top of a score this module already computed.
"""
import math
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import POLICY


def haversine_distance_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def check_geo_jump(db: Session, event: models.AttendanceEvent) -> Optional[dict]:
    """Flag if implied travel speed from the previous event is physically implausible."""
    if event.latitude is None or event.longitude is None:
        return None

    prev = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.employee_id == event.employee_id,
            models.AttendanceEvent.event_ts < event.event_ts,
            models.AttendanceEvent.latitude.isnot(None),
            models.AttendanceEvent.longitude.isnot(None),
            models.AttendanceEvent.id != event.id,
        )
        .order_by(models.AttendanceEvent.event_ts.desc())
        .first()
    )
    if not prev:
        return None

    hours = (event.event_ts - prev.event_ts).total_seconds() / 3600.0
    if hours <= 0:
        return None

    distance_km = haversine_distance_km(prev.latitude, prev.longitude, event.latitude, event.longitude)
    implied_speed = distance_km / hours
    max_plausible = POLICY["rules"]["geo_jump_max_plausible_kmh"]

    if implied_speed <= max_plausible:
        return None

    score = min(1.0, implied_speed / (max_plausible * 4))  # saturates at 4x threshold
    return {
        "flag_type": "GEO_JUMP",
        "score": round(score, 3),
        "details": {
            "implied_speed_kmh": round(implied_speed, 1),
            "distance_km": round(distance_km, 2),
            "hours_between_events": round(hours, 3),
            "prev_event_id": str(prev.id),
        },
    }


def check_same_device_multi_employee(db: Session, event: models.AttendanceEvent) -> Optional[dict]:
    """Flag if a different employee punched the same device within a very short window — possible buddy punching."""
    if event.device_id is None:
        return None

    window = timedelta(seconds=POLICY["rules"]["same_device_window_seconds"])
    nearby = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.device_id == event.device_id,
            models.AttendanceEvent.employee_id != event.employee_id,
            models.AttendanceEvent.event_ts >= event.event_ts - window,
            models.AttendanceEvent.event_ts <= event.event_ts + window,
        )
        .all()
    )
    if not nearby:
        return None

    return {
        "flag_type": "SAME_DEVICE_MULTI_EMPLOYEE",
        "score": 0.9,  # this pattern is inherently high-signal; not a graded score
        "details": {
            "other_employee_ids": [str(e.employee_id) for e in nearby],
            "other_event_ids": [str(e.id) for e in nearby],
            "window_seconds": POLICY["rules"]["same_device_window_seconds"],
        },
    }


def check_frequency_anomaly(db: Session, event: models.AttendanceEvent) -> Optional[dict]:
    """Flag if today's punch count for this employee deviates sharply from their trailing baseline."""
    baseline_days = POLICY["rules"]["frequency_baseline_days"]
    ratio_threshold = POLICY["rules"]["frequency_anomaly_ratio"]

    window_start = event.event_ts - timedelta(days=baseline_days)
    day_start = event.event_ts.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    today_count = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.employee_id == event.employee_id,
            models.AttendanceEvent.event_ts >= day_start,
            models.AttendanceEvent.event_ts < day_end,
        )
        .count()
    )

    total_in_window = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.employee_id == event.employee_id,
            models.AttendanceEvent.event_ts >= window_start,
            models.AttendanceEvent.event_ts < day_start,
        )
        .count()
    )
    distinct_days = baseline_days  # simplification: use full window as denominator
    baseline_avg = total_in_window / distinct_days if distinct_days else 0

    if baseline_avg < 0.5:
        return None  # not enough history to judge — avoid false positives on new hires

    if today_count <= baseline_avg * ratio_threshold and today_count >= baseline_avg / ratio_threshold:
        return None

    deviation_ratio = today_count / baseline_avg if baseline_avg else float("inf")
    score = min(1.0, abs(math.log2(max(deviation_ratio, 0.01))) / 4)

    return {
        "flag_type": "FREQUENCY_ANOMALY",
        "score": round(score, 3),
        "details": {
            "today_count": today_count,
            "baseline_avg_per_day": round(baseline_avg, 2),
            "baseline_window_days": baseline_days,
        },
    }


def run_all_rules(db: Session, event: models.AttendanceEvent) -> list[dict]:
    """Runs every deterministic rule and returns the list of triggered flags (may be empty)."""
    checks = [check_geo_jump, check_same_device_multi_employee, check_frequency_anomaly]
    results = []
    for check in checks:
        result = check(db, event)
        if result:
            results.append(result)
    return results
