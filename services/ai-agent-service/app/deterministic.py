"""
Deterministic fallback logic — runs unconditionally, LLM output (if any) is
layered on top of this rather than replacing it. Two responsibilities:

1. `deterministic_prescreen`: score a regularization request against the
   bundled policy doc's rules (Section 1/2 of policies/attendance_policy.md)
   using keyword matching and a repeat-offender count — no LLM required.
2. `parse_query_deterministic`: resolve a small set of canonical NL query
   patterns via regex, so the NL query endpoint still answers common
   questions with the LLM completely disabled.
"""
import re
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import POLICY

ACCEPTED_REASON_KEYWORDS = [
    "device malfunction", "device offline", "device down", "biometric",
    "work from home", "wfh", "medical", "emergency", "forgot badge",
    "forgot my badge", "credential", "travel", "client site", "manager approved",
]


def deterministic_prescreen(db: Session, employee_id, reason: str, target_date: date) -> dict:
    reason_lower = reason.lower()
    keyword_hit = any(kw in reason_lower for kw in ACCEPTED_REASON_KEYWORDS)

    window_start = target_date - timedelta(days=POLICY["regularization"]["repeat_offender_window_days"])
    recent_count = (
        db.query(models.RegularizationRequest)
        .filter(
            models.RegularizationRequest.employee_id == employee_id,
            models.RegularizationRequest.target_date >= window_start,
            models.RegularizationRequest.target_date <= target_date,
        )
        .count()
    )
    repeat_threshold = POLICY["regularization"]["repeat_offender_threshold"]
    is_repeat_offender = recent_count > repeat_threshold

    if is_repeat_offender:
        risk_level = "HIGH"
        confidence = 0.85
        recommendation = (
            f"Policy Section 2: employee has {recent_count} regularization requests in the trailing "
            f"{POLICY['regularization']['repeat_offender_window_days']} days, exceeding the threshold of "
            f"{repeat_threshold}. Flagged as a repeat pattern — recommend priority manager review rather "
            f"than streamlined approval, regardless of this reason's plausibility."
        )
    elif keyword_hit:
        risk_level = "LOW"
        confidence = 0.75
        recommendation = (
            "Policy Section 1: stated reason matches an accepted regularization category. "
            f"Employee has {recent_count} request(s) in the trailing "
            f"{POLICY['regularization']['repeat_offender_window_days']} days (within normal range). "
            "Recommend approval, pending manager confirmation."
        )
    else:
        risk_level = "MEDIUM"
        confidence = 0.5
        recommendation = (
            "Reason does not clearly match a Policy Section 1 accepted category. "
            f"Employee has {recent_count} request(s) in the trailing "
            f"{POLICY['regularization']['repeat_offender_window_days']} days. "
            "Recommend manager review the stated reason directly before deciding."
        )

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "risk_level": risk_level,
        "source": "DETERMINISTIC",
    }


# ---- NL query deterministic fallback ----

_LATE_PATTERN = re.compile(r"late.*more than (\d+)|more than (\d+).*late", re.IGNORECASE)
_ANOMALY_PATTERN = re.compile(r"anomal|flag", re.IGNORECASE)
_ABSENT_PATTERN = re.compile(r"absent", re.IGNORECASE)


def parse_query_deterministic(question: str) -> Optional[dict]:
    """Handles a small set of canonical question shapes without any LLM."""
    q = question.lower()

    late_match = _LATE_PATTERN.search(q)
    if late_match or "late" in q:
        threshold = None
        if late_match:
            threshold = int(late_match.group(1) or late_match.group(2))
        return {
            "metric": "LATE_COUNT",
            "department": None,
            "employee_code": None,
            "date_from": None,
            "date_to": None,
            "threshold": threshold,
        }

    if _ANOMALY_PATTERN.search(q):
        return {
            "metric": "ANOMALY_COUNT",
            "department": None,
            "employee_code": None,
            "date_from": None,
            "date_to": None,
            "threshold": None,
        }

    if _ABSENT_PATTERN.search(q):
        return {
            "metric": "ABSENT_COUNT",
            "department": None,
            "employee_code": None,
            "date_from": None,
            "date_to": None,
            "threshold": None,
        }

    return None


# ---- Report narrative deterministic fallback ----

def deterministic_report_narrative(stats: dict) -> str:
    """
    Plain-templated summary sentence built directly from already-computed
    stats — used whenever the LLM path is unavailable or returns nothing
    grounded. This is what guarantees a report always goes out with a
    coherent summary line, LLM or not.
    """
    return (
        f"{stats['total_checkins']} check-ins recorded from {stats['unique_employees']} employees "
        f"during this period. {stats['flagged_count']} events were flagged for review, "
        f"{stats['open_anomaly_count']} anomaly flags are currently open, and "
        f"{stats['regularizations_submitted']} regularization request(s) were submitted "
        f"({stats['regularizations_approved']} approved, {stats['regularizations_rejected']} rejected)."
    )
