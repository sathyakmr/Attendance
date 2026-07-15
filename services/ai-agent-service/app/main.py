import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models, schemas, audit, rules, llm_client, deterministic
from app.auth import get_current_claims, require_roles, require_service_key
from app.config import settings, POLICY, load_policy_doc_text
from app.database import get_db, engine, Base
from app.guardrails import sanitize, pii, grounding

app = FastAPI(
    title="AI Agent Service",
    description="Anomaly detection, regularization pre-screening, and guarded NL query.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine, checkfirst=True)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "llm_enabled": bool(settings.anthropic_api_key)}


# ---------------------------------------------------------------------------
# Anomaly detection — called by attendance-service after a check-in write.
# Deterministic rules ALWAYS run; the LLM only adds narrative on top and is
# never allowed to change rule_score or the routing decision.
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/agent/analyze-event",
    response_model=schemas.AnalyzeEventResponse,
    dependencies=[Depends(require_service_key)],
)
def analyze_event(payload: schemas.AnalyzeEventRequest, db: Session = Depends(get_db)):
    event = db.query(models.AttendanceEvent).filter_by(id=payload.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    triggered = rules.run_all_rules(db, event)
    created_flags = []
    routed_to_review = False

    for result in triggered:
        decision = grounding.route_anomaly(result["score"])

        llm_narrative = None
        llm_confidence = None
        if settings.anthropic_api_key:
            redacted_context, _ = pii.redact(str(result["details"]))
            llm_result = llm_client.explain_anomaly({
                "flag_type": result["flag_type"],
                "rule_score": result["score"],
                "details_redacted": redacted_context,
            })
            if llm_result:
                narrative = grounding.strip_ungrounded_claims(
                    llm_result.get("narrative", ""),
                    allowed_facts=[result["flag_type"], str(result["score"])],
                )
                if narrative:
                    llm_narrative = narrative
                    llm_confidence = 0.7  # advisory only; never gates routing

        flag = models.AnomalyFlag(
            attendance_event_id=event.id,
            employee_id=event.employee_id,
            flag_type=result["flag_type"],
            rule_score=result["score"],
            llm_narrative=llm_narrative,
            llm_confidence=llm_confidence,
            status=models.AnomalyFlagStatus.OPEN if decision.route != "AUTO" else models.AnomalyFlagStatus.CLEARED,
            details=result["details"],
        )
        db.add(flag)
        db.flush()

        audit.write_audit_entry(
            db, entity_type="anomaly_flag", entity_id=flag.id,
            actor_id="ai-agent", actor_role="SYSTEM_AGENT", action="CREATE",
            before_state=None,
            after_state={
                "flag_type": result["flag_type"],
                "rule_score": result["score"],
                "route": decision.route,
            },
        )

        if decision.route in ("REVIEW", "ESCALATE"):
            review_item = models.HumanReviewQueueItem(
                subject_type="ANOMALY_FLAG",
                subject_id=flag.id,
                employee_id=event.employee_id,
                priority=decision.priority,
                reason=f"{result['flag_type']} (rule_score={result['score']})"
                       + (f" — {llm_narrative}" if llm_narrative else ""),
                status=models.ReviewStatus.OPEN,
            )
            db.add(review_item)
            db.flush()
            audit.write_audit_entry(
                db, entity_type="human_review_queue", entity_id=review_item.id,
                actor_id="ai-agent", actor_role="SYSTEM_AGENT", action="ENQUEUE",
                before_state=None,
                after_state={"subject_type": "ANOMALY_FLAG", "priority": decision.priority},
            )
            routed_to_review = True

        created_flags.append(flag)

    db.commit()
    for f in created_flags:
        db.refresh(f)

    return schemas.AnalyzeEventResponse(
        event_id=event.id,
        flags_created=created_flags,
        routed_to_review=routed_to_review,
    )


# ---------------------------------------------------------------------------
# Regularization pre-screen — called by regularization-service on request
# creation. Always returns a result (deterministic at minimum); never blocks
# or gates the actual approval, which remains a human decision.
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/agent/prescreen-regularization",
    response_model=schemas.PrescreenResponse,
    dependencies=[Depends(require_service_key)],
)
def prescreen_regularization(payload: schemas.PrescreenRequest, db: Session = Depends(get_db)):
    sanitize_result = sanitize.sanitize(payload.reason, max_length=2000)
    if not sanitize_result.allowed:
        # Don't silently drop a suspicious submission — route straight to human review
        # rather than attempting to interpret it further with either engine.
        return schemas.PrescreenResponse(
            recommendation=f"Input flagged by guardrail ({sanitize_result.reason}); routed directly to manager review without AI analysis.",
            confidence=0.0,
            risk_level="HIGH",
            source="DETERMINISTIC",
        )

    det_result = deterministic.deterministic_prescreen(db, payload.employee_id, payload.reason, payload.target_date)

    if settings.anthropic_api_key:
        redacted_reason, _ = pii.redact(payload.reason)
        llm_result = llm_client.prescreen_regularization(
            redacted_context={
                "reason": redacted_reason,
                "target_date": str(payload.target_date),
                "requested_event_type": payload.requested_event_type,
                "deterministic_risk_level": det_result["risk_level"],
            },
            policy_text=load_policy_doc_text(),
        )
        if llm_result:
            return schemas.PrescreenResponse(
                recommendation=llm_result["recommendation"],
                confidence=float(llm_result["confidence"]),
                risk_level=llm_result["risk_level"],
                source="LLM",
            )

    return schemas.PrescreenResponse(**det_result)


# ---------------------------------------------------------------------------
# Natural-language query — role-gated, read-only, guarded end to end.
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/agent/query",
    response_model=schemas.NLQueryResponse,
    dependencies=[Depends(require_roles(*POLICY["nl_query"]["allowed_roles"]))],
)
def nl_query(payload: schemas.NLQueryRequest, db: Session = Depends(get_db)):
    sanitize_result = sanitize.sanitize(payload.question, max_length=POLICY["nl_query"]["max_question_length"])
    if not sanitize_result.allowed:
        return schemas.NLQueryResponse(
            answer="This question could not be processed due to an input safety check. Please rephrase.",
            metric=None, result_count=None, grounded=False, source="REJECTED",
        )

    intent = None
    source = "DETERMINISTIC_PARSE"
    if settings.anthropic_api_key:
        intent = llm_client.parse_query_intent(payload.question)
        if intent:
            source = "LLM_INTENT"

    if not intent:
        intent = deterministic.parse_query_deterministic(payload.question)

    if not intent or not intent.get("metric"):
        return schemas.NLQueryResponse(
            answer="I couldn't map this question to a supported metric (late count, absent count, "
                   "flagged count, or anomaly count). Try rephrasing, e.g. 'who was late more than 3 times this month'.",
            metric=None, result_count=None, grounded=False, source=source,
        )

    # Build a parametrized query from the structured intent — never from raw text.
    metric = intent["metric"]
    if metric == "LATE_COUNT" or metric == "FLAGGED_COUNT":
        count = db.query(models.AttendanceEvent).filter(models.AttendanceEvent.status == "FLAGGED").count()
        answer = f"There are currently {count} flagged (late/irregular) attendance events on record."
    elif metric == "ANOMALY_COUNT":
        count = db.query(models.AnomalyFlag).filter(models.AnomalyFlag.status == "OPEN").count()
        answer = f"There are currently {count} open anomaly flags awaiting review."
    elif metric == "ABSENT_COUNT":
        count = 0  # No absence/leave table exists yet in this phase — deliberately grounded to zero rather than guessed.
        answer = "Absence tracking isn't implemented yet in this phase — no leave/absence table exists to query."
    else:
        count = None
        answer = "Unsupported metric."

    return schemas.NLQueryResponse(
        answer=answer, metric=metric, result_count=count, grounded=True, source=source,
    )


@app.post(
    "/api/v1/agent/summarize-report",
    dependencies=[Depends(require_service_key)],
)
def summarize_report(stats: dict):
    """
    Called by reporting-service with already-computed statistics. Always
    returns a usable narrative: LLM-phrased if available and grounded,
    deterministic-templated otherwise. Never computes any number itself.
    """
    narrative = None
    source = "DETERMINISTIC"
    if settings.anthropic_api_key:
        llm_narrative = llm_client.summarize_report(stats)
        if llm_narrative:
            expected_facts = [str(v) for v in stats.values()]
            grounded = grounding.strip_ungrounded_claims(llm_narrative, allowed_facts=expected_facts)
            if grounded:
                narrative = grounded
                source = "LLM"

    if not narrative:
        narrative = deterministic.deterministic_report_narrative(stats)

    return {"narrative": narrative, "source": source}


# ---------------------------------------------------------------------------
# Human review queue
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/agent/review-queue",
    response_model=List[schemas.ReviewQueueItemResponse],
    dependencies=[Depends(require_roles("MANAGER", "HR_ADMIN", "SUPER_ADMIN"))],
)
def list_review_queue(db: Session = Depends(get_db)):
    return (
        db.query(models.HumanReviewQueueItem)
        .filter_by(status=models.ReviewStatus.OPEN)
        .order_by(models.HumanReviewQueueItem.priority.desc(), models.HumanReviewQueueItem.created_at.asc())
        .all()
    )


@app.post(
    "/api/v1/agent/review-queue/{item_id}/resolve",
    response_model=schemas.ReviewQueueItemResponse,
    dependencies=[Depends(require_roles("MANAGER", "HR_ADMIN", "SUPER_ADMIN"))],
)
def resolve_review_item(
    item_id: uuid.UUID,
    payload: schemas.ResolveReviewRequest,
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    item = db.query(models.HumanReviewQueueItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != models.ReviewStatus.OPEN:
        raise HTTPException(status_code=409, detail="Item already resolved")

    before = {"status": item.status.value}
    item.status = models.ReviewStatus.RESOLVED
    item.resolution = payload.resolution
    item.resolution_notes = payload.notes
    item.resolved_by = claims["sub"]
    item.resolved_at = datetime.now(timezone.utc)
    db.flush()

    audit.write_audit_entry(
        db, entity_type="human_review_queue", entity_id=item.id,
        actor_id=claims["sub"], actor_role=claims["role"], action="RESOLVE",
        before_state=before, after_state={"resolution": payload.resolution, "notes": payload.notes},
    )

    # If this was an anomaly flag confirmed as real, propagate the decision:
    # mark the underlying flag CONFIRMED, and ask attendance-service (the
    # sole ledger writer) to reject the underlying event.
    if item.subject_type == "ANOMALY_FLAG":
        flag = db.query(models.AnomalyFlag).filter_by(id=item.subject_id).first()
        if flag:
            flag_before = {"status": flag.status.value}
            flag.status = models.AnomalyFlagStatus.CONFIRMED if payload.resolution == "CONFIRMED" else models.AnomalyFlagStatus.CLEARED
            flag.resolved_at = datetime.now(timezone.utc)
            db.flush()
            audit.write_audit_entry(
                db, entity_type="anomaly_flag", entity_id=flag.id,
                actor_id=claims["sub"], actor_role=claims["role"], action="RESOLVE",
                before_state=flag_before, after_state={"status": flag.status.value},
            )

            if payload.resolution == "CONFIRMED":
                try:
                    resp = httpx.patch(
                        f"{settings.attendance_service_url}/api/v1/internal/attendance-events/{flag.attendance_event_id}/status",
                        headers={"X-API-Key": settings.attendance_service_api_key},
                        json={
                            "status": "REJECTED",
                            "actor_id": claims["sub"],
                            "actor_role": claims["role"],
                            "reason": f"Confirmed anomaly via human review: {payload.notes or flag.flag_type}",
                        },
                        timeout=10.0,
                    )
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    # Review resolution itself already succeeded and is audited;
                    # surface the propagation failure without losing the decision.
                    db.commit()
                    raise HTTPException(
                        status_code=502,
                        detail=f"Review resolved, but ledger status update failed: {exc}",
                    )

    db.commit()
    db.refresh(item)
    return item
