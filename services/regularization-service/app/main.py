import uuid
from datetime import datetime, timezone, date as date_type
from typing import List, Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models, schemas, audit
from app.auth import get_current_claims, require_roles
from app.config import settings
from app.database import get_db, engine, Base

app = FastAPI(
    title="Regularization Service",
    description="Employee request -> manager approval -> audit trail -> ledger update.",
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
    return {"status": "ok"}


def _employee_for_user(db: Session, claims: dict) -> models.Employee:
    if not claims.get("employee_id"):
        raise HTTPException(status_code=400, detail="This account has no linked employee record")
    employee = db.query(models.Employee).filter_by(id=claims["employee_id"]).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Linked employee record not found")
    return employee


# ---------------------------------------------------------------------------
# Employee: submit a regularization request
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/regularizations",
    response_model=schemas.RegularizationResponse,
    dependencies=[Depends(require_roles("EMPLOYEE", "MANAGER"))],  # managers are employees too and can self-file
)
def create_regularization(
    payload: schemas.RegularizationCreateRequest,
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    employee = _employee_for_user(db, claims)

    if payload.original_event_id:
        original = (
            db.query(models.AttendanceEvent)
            .filter_by(id=payload.original_event_id, employee_id=employee.id)
            .first()
        )
        if not original:
            raise HTTPException(status_code=404, detail="original_event_id not found for this employee")

    req = models.RegularizationRequest(
        employee_id=employee.id,
        target_date=payload.target_date,
        requested_event_type=payload.requested_event_type,
        requested_time=payload.requested_time,
        reason=payload.reason,
        original_event_id=payload.original_event_id,
        status=models.RegularizationStatus.PENDING,
    )
    db.add(req)
    db.flush()

    audit.write_audit_entry(
        db, entity_type="regularization_request", entity_id=req.id,
        actor_id=claims["sub"], actor_role=claims["role"], action="SUBMIT",
        before_state=None,
        after_state={
            "employee_code": employee.employee_code,
            "target_date": str(payload.target_date),
            "requested_event_type": payload.requested_event_type,
            "reason": payload.reason,
        },
    )
    db.commit()
    db.refresh(req)

    # Best-effort AI pre-screen — matches the design doc's Section 4 flowchart
    # ("AI Agent pre-screen") step. Never blocks submission and never gates
    # the manager's ability to decide; a failure here just leaves the
    # request PENDING instead of AI_PRESCREENED, which the deterministic
    # workflow handles identically either way.
    try:
        resp = httpx.post(
            f"{settings.ai_agent_service_url}/api/v1/agent/prescreen-regularization",
            headers={"X-API-Key": settings.ai_agent_service_api_key},
            json={
                "request_id": str(req.id),
                "employee_id": str(employee.id),
                "employee_code": employee.employee_code,
                "target_date": str(payload.target_date),
                "requested_event_type": payload.requested_event_type,
                "requested_time": str(payload.requested_time),
                "reason": payload.reason,
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        prescreen = resp.json()
        req.ai_recommendation = prescreen["recommendation"]
        req.ai_confidence = prescreen["confidence"]
        req.status = models.RegularizationStatus.AI_PRESCREENED
        db.flush()
        audit.write_audit_entry(
            db, entity_type="regularization_request", entity_id=req.id,
            actor_id="ai-agent", actor_role="SYSTEM_AGENT", action="PRESCREEN",
            before_state={"status": "PENDING"},
            after_state={"status": "AI_PRESCREENED", "risk_level": prescreen["risk_level"], "confidence": prescreen["confidence"]},
        )
        db.commit()
        db.refresh(req)
    except httpx.HTTPError:
        pass  # request remains PENDING; manager can still decide without an AI recommendation

    return req


# ---------------------------------------------------------------------------
# Read: list / detail, scoped by role
# ---------------------------------------------------------------------------

@app.get("/api/v1/regularizations", response_model=List[schemas.RegularizationResponse])
def list_regularizations(
    status_filter: Optional[str] = Query(None, alias="status"),
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    q = db.query(models.RegularizationRequest)

    if claims["role"] == "HR_ADMIN" or claims["role"] == "SUPER_ADMIN":
        pass  # org-wide visibility
    elif claims["role"] == "MANAGER":
        manager_employee = _employee_for_user(db, claims)
        direct_report_ids = [
            e.id for e in db.query(models.Employee).filter_by(manager_id=manager_employee.id).all()
        ]
        # Managers also see their own submissions
        direct_report_ids.append(manager_employee.id)
        q = q.filter(models.RegularizationRequest.employee_id.in_(direct_report_ids))
    else:  # EMPLOYEE
        employee = _employee_for_user(db, claims)
        q = q.filter(models.RegularizationRequest.employee_id == employee.id)

    if status_filter:
        q = q.filter(models.RegularizationRequest.status == status_filter)

    return q.order_by(models.RegularizationRequest.created_at.desc()).all()


def _assert_can_view(req: models.RegularizationRequest, claims: dict, db: Session):
    if claims["role"] in ("HR_ADMIN", "SUPER_ADMIN"):
        return
    if claims.get("employee_id") == str(req.employee_id):
        return
    if claims["role"] == "MANAGER":
        requester = db.query(models.Employee).filter_by(id=req.employee_id).first()
        if requester and str(requester.manager_id) == claims.get("employee_id"):
            return
    raise HTTPException(status_code=403, detail="Not authorized to view this request")


@app.get("/api/v1/regularizations/{request_id}", response_model=schemas.RegularizationResponse)
def get_regularization(request_id: uuid.UUID, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    req = db.query(models.RegularizationRequest).filter_by(id=request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _assert_can_view(req, claims, db)
    return req


# ---------------------------------------------------------------------------
# Manager/HR: decision
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/regularizations/{request_id}/decision",
    response_model=schemas.RegularizationResponse,
    dependencies=[Depends(require_roles("MANAGER", "HR_ADMIN", "SUPER_ADMIN"))],
)
def decide_regularization(
    request_id: uuid.UUID,
    payload: schemas.RegularizationDecisionRequest,
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    req = db.query(models.RegularizationRequest).filter_by(id=request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status not in (models.RegularizationStatus.PENDING, models.RegularizationStatus.AI_PRESCREENED):
        raise HTTPException(status_code=409, detail=f"Request already {req.status.value}")

    requester = db.query(models.Employee).filter_by(id=req.employee_id).first()

    # RBAC: a MANAGER may only decide requests from their own direct reports.
    # HR_ADMIN / SUPER_ADMIN can decide any request (break-glass / escalation path).
    if claims["role"] == "MANAGER":
        if not requester or str(requester.manager_id) != claims.get("employee_id"):
            raise HTTPException(status_code=403, detail="Not the manager of record for this employee")
        if str(req.employee_id) == claims.get("employee_id"):
            raise HTTPException(status_code=403, detail="Managers cannot approve their own requests")

    before_state = {"status": req.status.value}

    if payload.decision == "REJECT":
        req.status = models.RegularizationStatus.REJECTED
        req.decided_by = claims["sub"]
        req.decision_notes = payload.notes
        req.decided_at = datetime.now(timezone.utc)
        db.flush()
        audit.write_audit_entry(
            db, entity_type="regularization_request", entity_id=req.id,
            actor_id=claims["sub"], actor_role=claims["role"], action="REJECT",
            before_state=before_state, after_state={"status": "REJECTED", "notes": payload.notes},
        )
        db.commit()
        db.refresh(req)
        return req

    if payload.decision == "ESCALATE":
        req.status = models.RegularizationStatus.ESCALATED
        req.decided_by = claims["sub"]
        req.decision_notes = payload.notes
        req.decided_at = datetime.now(timezone.utc)
        db.flush()
        audit.write_audit_entry(
            db, entity_type="regularization_request", entity_id=req.id,
            actor_id=claims["sub"], actor_role=claims["role"], action="ESCALATE",
            before_state=before_state, after_state={"status": "ESCALATED", "notes": payload.notes},
        )
        db.commit()
        db.refresh(req)
        return req

    # APPROVE — call attendance-service, the single writer of ledger truth
    event_ts = datetime.combine(req.target_date, req.requested_time).replace(tzinfo=timezone.utc)
    try:
        resp = httpx.post(
            f"{settings.attendance_service_url}/api/v1/internal/regularization-correction",
            headers={"X-API-Key": settings.attendance_service_api_key},
            json={
                "employee_code": requester.employee_code,
                "event_type": req.requested_event_type.value if hasattr(req.requested_event_type, "value") else req.requested_event_type,
                "event_ts": event_ts.isoformat(),
                "original_event_id": str(req.original_event_id) if req.original_event_id else None,
                "actor_id": claims["sub"],
                "actor_role": claims["role"],
                "decision_notes": payload.notes,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Ledger update failed, request left PENDING: {exc}")

    new_event = resp.json()

    req.status = models.RegularizationStatus.APPROVED
    req.decided_by = claims["sub"]
    req.decision_notes = payload.notes
    req.decided_at = datetime.now(timezone.utc)
    req.new_event_id = new_event["id"]
    db.flush()

    audit.write_audit_entry(
        db, entity_type="regularization_request", entity_id=req.id,
        actor_id=claims["sub"], actor_role=claims["role"], action="APPROVE",
        before_state=before_state,
        after_state={"status": "APPROVED", "notes": payload.notes, "new_event_id": new_event["id"]},
    )
    db.commit()
    db.refresh(req)
    return req
