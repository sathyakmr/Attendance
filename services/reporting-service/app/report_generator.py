"""
Orchestrates one full report cycle: aggregate -> summarize -> send -> persist.

Every step degrades gracefully:
  - aggregation is pure SQL, always succeeds if the DB is reachable
  - summarization calls ai-agent-service best-effort; on any failure, falls
    back to a plain local template (never blocks report delivery on the
    agent being available)
  - sending goes through whatsapp_client, which itself has a mock fallback
    and built-in retry
  - the notification row is written regardless of send outcome, so a failed
    delivery is never silently lost — it's visible via GET /api/v1/reports
    with status=FAILED and a populated last_error
"""
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app import models, aggregation, whatsapp_client, audit
from app.config import settings

logger = logging.getLogger("reporting.generator")


def _local_fallback_narrative(stats: dict) -> str:
    """Used only if even the ai-agent-service call itself fails entirely
    (network error, service down) — not just if its LLM path is unavailable,
    since ai-agent-service already has its own deterministic fallback for that."""
    return (
        f"{stats['total_checkins']} check-ins from {stats['unique_employees']} employees. "
        f"{stats['flagged_count']} flagged events, {stats['open_anomaly_count']} open anomalies. "
        f"{stats['regularizations_submitted']} regularization request(s) "
        f"({stats['regularizations_approved']} approved, {stats['regularizations_rejected']} rejected)."
    )


def get_summary(stats: dict) -> tuple[str, str]:
    """Returns (narrative, source). source is 'LLM' | 'DETERMINISTIC' | 'LOCAL_FALLBACK'."""
    try:
        resp = httpx.post(
            f"{settings.ai_agent_service_url}/api/v1/agent/summarize-report",
            headers={"X-API-Key": settings.ai_agent_service_api_key},
            json=stats,
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["narrative"], data["source"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai-agent-service summarize-report call failed, using local fallback: %s", exc)
        return _local_fallback_narrative(stats), "LOCAL_FALLBACK"


def generate_and_send_report(db: Session, period_type: str, reference_time: datetime) -> models.Notification:
    period_start, period_end = aggregation.compute_period_bounds(period_type, reference_time)
    stats = aggregation.aggregate_stats(db, period_start, period_end)
    narrative, source = get_summary(stats)

    header = f"Attendance Report ({period_type.title()}) — {period_start.date()} to {period_end.date()}"
    message_text = f"{header}\n\n{narrative}"

    notification_id = str(uuid.uuid4())
    notification = models.Notification(
        notification_id=notification_id,
        channel=models.NotificationChannel.WHATSAPP,
        recipient=settings.whatsapp_to_number or "(unset — mock mode)",
        report_period=models.ReportPeriod(period_type),
        period_start=period_start,
        period_end=period_end,
        payload_summary=message_text,
        status=models.NotificationStatus.PENDING,
    )
    db.add(notification)
    db.flush()

    audit.write_audit_entry(
        db, entity_type="notification", entity_id=notification.id,
        actor_id="scheduler" , actor_role="SYSTEM", action="CREATE",
        before_state=None,
        after_state={"period_type": period_type, "stats": stats, "summary_source": source},
    )
    db.commit()

    result, attempts = whatsapp_client.send_with_retry(message_text)

    before = {"status": notification.status.value, "attempt_count": notification.attempt_count}
    notification.attempt_count = attempts
    notification.last_attempt_at = datetime.now(timezone.utc)

    if result.success:
        notification.status = models.NotificationStatus.SENT
        notification.whatsapp_message_id = result.external_message_id
        notification.sent_at = datetime.now(timezone.utc)
        notification.last_error = None
    else:
        notification.status = models.NotificationStatus.FAILED
        notification.last_error = result.error
        logger.error(
            "WhatsApp delivery failed after %d attempts for notification %s: %s. "
            "Fallback channel (email/SMS) is not implemented in this phase — "
            "logging failure for manual follow-up.",
            attempts, notification_id, result.error,
        )

    db.flush()
    audit.write_audit_entry(
        db, entity_type="notification", entity_id=notification.id,
        actor_id="whatsapp_client", actor_role="SYSTEM", action="SEND_ATTEMPT",
        before_state=before,
        after_state={
            "status": notification.status.value,
            "attempts": attempts,
            "mode": result.mode,
            "whatsapp_message_id": notification.whatsapp_message_id,
            "error": notification.last_error,
        },
    )
    db.commit()
    db.refresh(notification)
    return notification
