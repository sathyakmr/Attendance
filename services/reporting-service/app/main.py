import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import models, schemas, audit
from app.config import settings
from app.database import get_db, engine, Base
from app.report_generator import generate_and_send_report
from app.scheduler import start_scheduler, stop_scheduler
from app.webhook_security import verify_signature

logger = logging.getLogger("reporting.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Reporting Service",
    description="Scheduled attendance report generation and WhatsApp delivery.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "whatsapp_mode": "LIVE" if settings.whatsapp_access_token else "MOCK",
        "scheduler_enabled": settings.scheduler_enabled,
    }


# ---------------------------------------------------------------------------
# Report generation — manual trigger (also invoked internally by the scheduler)
# ---------------------------------------------------------------------------

@app.post("/api/v1/reports/generate", response_model=schemas.NotificationResponse)
def generate_report(payload: schemas.GenerateReportRequest, db: Session = Depends(get_db)):
    reference_time = payload.reference_time or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    notification = generate_and_send_report(db, payload.period_type, reference_time)
    return notification


@app.get("/api/v1/reports", response_model=List[schemas.NotificationResponse])
def list_reports(
    period_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    q = db.query(models.Notification)
    if period_type:
        q = q.filter(models.Notification.report_period == period_type)
    if status_filter:
        q = q.filter(models.Notification.status == status_filter)
    return q.order_by(models.Notification.created_at.desc()).all()


@app.get("/api/v1/reports/{notification_id}", response_model=schemas.NotificationResponse)
def get_report(notification_id: uuid.UUID, db: Session = Depends(get_db)):
    notification = db.query(models.Notification).filter_by(id=notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@app.post("/api/v1/reports/{notification_id}/resend", response_model=schemas.NotificationResponse)
def resend_report(notification_id: uuid.UUID, db: Session = Depends(get_db)):
    """Manually retry a FAILED notification — re-sends the same stored summary text
    rather than recomputing it, so the report content stays consistent with what
    was originally generated for that period."""
    from app import whatsapp_client

    notification = db.query(models.Notification).filter_by(id=notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.status not in (models.NotificationStatus.FAILED,):
        raise HTTPException(status_code=409, detail=f"Only FAILED notifications can be resent (current status: {notification.status.value})")

    before = {"status": notification.status.value, "attempt_count": notification.attempt_count}
    result, attempts = whatsapp_client.send_with_retry(notification.payload_summary)

    notification.attempt_count += attempts
    notification.last_attempt_at = datetime.now(timezone.utc)
    if result.success:
        notification.status = models.NotificationStatus.SENT
        notification.whatsapp_message_id = result.external_message_id
        notification.sent_at = datetime.now(timezone.utc)
        notification.last_error = None
    else:
        notification.status = models.NotificationStatus.FAILED
        notification.last_error = result.error

    db.flush()
    audit.write_audit_entry(
        db, entity_type="notification", entity_id=notification.id,
        actor_id="manual_resend", actor_role="SYSTEM", action="RESEND",
        before_state=before, after_state={"status": notification.status.value, "attempts": attempts},
    )
    db.commit()
    db.refresh(notification)
    return notification


# ---------------------------------------------------------------------------
# WhatsApp inbound webhook — verification handshake (GET) + delivery status
# callbacks (POST), per Meta's Cloud API webhook contract.
# ---------------------------------------------------------------------------

@app.get("/webhooks/whatsapp")
def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_webhook_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@app.post("/webhooks/whatsapp")
async def whatsapp_delivery_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    # Meta's webhook payload nests status updates under entry[].changes[].value.statuses[]
    updated_count = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for status_update in change.get("value", {}).get("statuses", []):
                wamid = status_update.get("id")
                new_status = status_update.get("status")  # 'sent' | 'delivered' | 'read' | 'failed'
                if not wamid or not new_status:
                    continue

                notification = db.query(models.Notification).filter_by(whatsapp_message_id=wamid).first()
                if not notification:
                    logger.warning("Delivery webhook for unknown wamid: %s", wamid)
                    continue

                before = {"status": notification.status.value}
                now = datetime.now(timezone.utc)

                if new_status == "delivered":
                    notification.status = models.NotificationStatus.DELIVERED
                    notification.delivered_at = now
                elif new_status == "read":
                    notification.status = models.NotificationStatus.READ
                    notification.read_at = now
                elif new_status == "failed":
                    notification.status = models.NotificationStatus.FAILED
                    errors = status_update.get("errors", [])
                    notification.last_error = str(errors[0]) if errors else "Delivery failed (per webhook)"
                # 'sent' is already the status set at initial send time; no-op here.

                db.flush()
                audit.write_audit_entry(
                    db, entity_type="notification", entity_id=notification.id,
                    actor_id="whatsapp_webhook", actor_role="SYSTEM", action="DELIVERY_STATUS_UPDATE",
                    before_state=before, after_state={"status": notification.status.value, "webhook_status": new_status},
                )
                updated_count += 1

    db.commit()
    return {"status": "ok", "updated": updated_count}
