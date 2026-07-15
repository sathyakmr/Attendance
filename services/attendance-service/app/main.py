import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas, validation, audit, dateranges
from app.config import settings
from app.database import get_db, engine, Base

app = FastAPI(
    title="Attendance Service",
    description="Core attendance capture, validation, and ledger storage.",
    version="0.1.0",
)

# CORS: permissive for local development so the browser-based frontend
# (running on its own origin) can call this API directly. A production
# deployment should restrict this to the actual frontend origin(s) and
# route through the API gateway from the design doc rather than exposing
# every service to the browser individually.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # Tables are created by init-db/001_init.sql on first Postgres boot.
    # create_all here is a no-op safety net for any model not yet in the SQL
    # init script (keeps local dev resilient if schema drifts during work).
    Base.metadata.create_all(bind=engine, checkfirst=True)


def require_api_key(x_api_key: str = Header(...)):
    """
    Minimal service-to-service auth placeholder. This is NOT the RBAC system
    (Section 8.5 of the design doc) — that's a separate phase. This just
    stops the local API from being wide open while we build.
    """
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Employees (minimal CRUD — full Employee/Org service comes in a later phase)
# ---------------------------------------------------------------------------

@app.post("/api/v1/employees", response_model=schemas.EmployeeResponse, dependencies=[Depends(require_api_key)])
def create_employee(payload: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Employee).filter_by(employee_code=payload.employee_code).first()
    if existing:
        raise HTTPException(status_code=409, detail="employee_code already exists")

    employee = models.Employee(
        employee_code=payload.employee_code,
        full_name=payload.full_name,
        department=payload.department,
        shift_start=payload.shift_start,
        shift_end=payload.shift_end,
        grace_minutes=payload.grace_minutes,
        geofence_lat=payload.geofence_lat,
        geofence_lng=payload.geofence_lng,
        geofence_radius_m=payload.geofence_radius_m,
    )
    db.add(employee)
    db.flush()

    audit.write_audit_entry(
        db, entity_type="employee", entity_id=employee.id,
        actor_id="system", actor_role="ADMIN", action="CREATE",
        before_state=None, after_state={"employee_code": employee.employee_code, "full_name": employee.full_name},
    )
    db.commit()
    db.refresh(employee)
    return employee


@app.post(
    "/api/v1/employees/{employee_code}/face-enroll",
    response_model=schemas.EmployeeResponse,
    dependencies=[Depends(require_api_key)],
)
def enroll_face(employee_code: str, payload: schemas.FaceEnrollRequest, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter_by(employee_code=employee_code).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    was_already_enrolled = employee.face_descriptor is not None
    employee.face_descriptor = payload.descriptor
    employee.face_enrolled_at = datetime.now(timezone.utc)
    db.flush()

    # Deliberately do NOT store the descriptor itself in the audit log —
    # duplicating a biometric template into a second table defeats the
    # point of scoping it narrowly in the first place. The audit trail
    # records that enrollment happened, not the biometric data itself.
    audit.write_audit_entry(
        db, entity_type="employee", entity_id=employee.id,
        actor_id="hr_admin_action", actor_role="HR_ADMIN", action="FACE_RE_ENROLL" if was_already_enrolled else "FACE_ENROLL",
        before_state={"was_enrolled": was_already_enrolled},
        after_state={"employee_code": employee_code, "enrolled_at": employee.face_enrolled_at.isoformat()},
    )
    db.commit()
    db.refresh(employee)
    return employee


# ---------------------------------------------------------------------------
# Face recognition — matching-data feed consumed by the frontend's
# client-side 1:N matcher. IMPORTANT: this route is registered BEFORE
# GET /api/v1/employees/{employee_code} below on purpose — FastAPI/Starlette
# matches path routes in registration order, and "face-descriptors" would
# otherwise be swallowed by the {employee_code} route (matching it as if it
# were an employee_code value) and never be reached. See the SECURITY NOTE
# in init-db/005_face_recognition.sql for why this is a separate, narrowly
# scoped endpoint from the general employee directory: ordinary
# roster/directory calls must never carry biometric data. This endpoint is
# still unauthenticated because client-side matching requires the browser
# to have the descriptors locally to compare against — that's the concrete
# cost of the "client-side, weaker security" choice over a server-side
# biometric-service (which would keep descriptors server-side and only ever
# return a match decision, never the raw vectors).
# ---------------------------------------------------------------------------

@app.get("/api/v1/employees/face-descriptors", response_model=List[schemas.FaceDescriptorEntry])
def list_face_descriptors(db: Session = Depends(get_db)):
    employees = (
        db.query(models.Employee)
        .filter(models.Employee.is_active == True, models.Employee.face_descriptor.isnot(None))  # noqa: E712
        .all()
    )
    return [
        schemas.FaceDescriptorEntry(
            id=e.id, employee_code=e.employee_code, full_name=e.full_name, descriptor=e.face_descriptor
        )
        for e in employees
    ]


@app.get("/api/v1/employees/{employee_code}", response_model=schemas.EmployeeResponse)
def get_employee(employee_code: str, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter_by(employee_code=employee_code).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@app.get("/api/v1/employees", response_model=List[schemas.EmployeeResponse])
def list_employees(
    manager_id: Optional[uuid.UUID] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Read-only directory listing. Used by the frontend to resolve an
    employee_id (from a JWT) to an employee_code (attendance-service's
    lookup key), and to render manager/HR team rosters. No write
    capability here — creation still goes through the API-key-gated
    POST /api/v1/employees above.
    """
    q = db.query(models.Employee)
    if manager_id:
        q = q.filter_by(manager_id=manager_id)
    if department:
        q = q.filter_by(department=department)
    return q.order_by(models.Employee.employee_code).all()


# ---------------------------------------------------------------------------
# HR dashboard — summary cards, live feed, history table, employee drawer.
# All read-only; no new write paths introduced by this section.
# ---------------------------------------------------------------------------

@app.get("/api/v1/dashboard/summary", response_model=schemas.DashboardSummaryResponse)
def dashboard_summary(db: Session = Depends(get_db)):
    today_start, today_end = dateranges.resolve_preset("TODAY")

    total_employees = db.query(models.Employee).filter(models.Employee.is_active == True).count()  # noqa: E712

    present_today = (
        db.query(models.AttendanceEvent.employee_id)
        .filter(
            models.AttendanceEvent.event_type == models.EventType.CHECK_IN,
            models.AttendanceEvent.event_ts >= today_start,
            models.AttendanceEvent.event_ts <= today_end,
            models.AttendanceEvent.status != models.EventStatus.REJECTED,
        )
        .distinct()
        .count()
    )
    absent_today = max(total_employees - present_today, 0)

    late_today = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.event_type == models.EventType.CHECK_IN,
            models.AttendanceEvent.event_ts >= today_start,
            models.AttendanceEvent.event_ts <= today_end,
            models.AttendanceEvent.status == models.EventStatus.FLAGGED,
        )
        .count()
    )

    face_enrolled = (
        db.query(models.Employee)
        .filter(models.Employee.is_active == True, models.Employee.face_descriptor.isnot(None))  # noqa: E712
        .count()
    )

    pending_regularization = (
        db.query(models.RegularizationRequest)
        .filter(models.RegularizationRequest.status.in_(["PENDING", "AI_PRESCREENED"]))
        .count()
    )

    return schemas.DashboardSummaryResponse(
        totalEmployees=total_employees,
        presentToday=present_today,
        absentToday=absent_today,
        lateToday=late_today,
        faceEnrolled=face_enrolled,
        pendingRegularization=pending_regularization,
    )


# ---------------------------------------------------------------------------
# Attendance capture — the critical write path
# ---------------------------------------------------------------------------

@app.post("/api/v1/checkin", response_model=schemas.AttendanceEventResponse, dependencies=[Depends(require_api_key)])
def checkin(payload: schemas.CheckInRequest, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter_by(employee_code=payload.employee_code, is_active=True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Active employee not found")

    device = None
    if payload.device_code:
        device = db.query(models.Device).filter_by(device_code=payload.device_code, is_active=True).first()
        if not device:
            raise HTTPException(status_code=404, detail="Active device not found")

    event_ts = payload.event_ts or datetime.now(timezone.utc)
    if event_ts.tzinfo is None:
        event_ts = event_ts.replace(tzinfo=timezone.utc)

    result = validation.validate_event(
        db, employee, payload.event_type, event_ts, payload.latitude, payload.longitude
    )

    event = models.AttendanceEvent(
        employee_id=employee.id,
        device_id=device.id if device else None,
        event_type=payload.event_type,
        source=payload.source,
        event_ts=event_ts,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=result.status,
        validation_notes=result.notes,
    )
    db.add(event)
    db.flush()

    if result.status == models.EventStatus.REJECTED:
        audit.write_audit_entry(
            db, entity_type="attendance_event", entity_id=event.id,
            actor_id=f"device:{payload.device_code or payload.source}", actor_role="DEVICE",
            action="REJECT", before_state=None,
            after_state={"reason": result.notes, "employee_code": employee.employee_code},
        )
        db.commit()
        raise HTTPException(status_code=409, detail=result.notes)

    audit.write_audit_entry(
        db, entity_type="attendance_event", entity_id=event.id,
        actor_id=f"device:{payload.device_code or payload.source}", actor_role="DEVICE",
        action="CREATE",
        before_state=None,
        after_state={
            "employee_code": employee.employee_code,
            "event_type": payload.event_type,
            "status": result.status.value,
            "notes": result.notes,
        },
    )
    db.commit()
    db.refresh(event)

    # Best-effort, non-blocking hand-off to the AI agent for anomaly analysis.
    # Per the design doc, the AI layer must never sit in the critical write
    # path: any failure here is swallowed so the check-in response is
    # unaffected either way.
    try:
        httpx.post(
            f"{settings.ai_agent_service_url}/api/v1/agent/analyze-event",
            headers={"X-API-Key": settings.api_key},
            json={"event_id": str(event.id)},
            timeout=3.0,
        )
    except Exception:
        pass

    return event


@app.get("/api/v1/employees/{employee_code}/attendance", response_model=List[schemas.AttendanceEventResponse])
def get_attendance_history(
    employee_code: str,
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    employee = db.query(models.Employee).filter_by(employee_code=employee_code).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    q = db.query(models.AttendanceEvent).filter(models.AttendanceEvent.employee_id == employee.id)
    if start:
        q = q.filter(models.AttendanceEvent.event_ts >= start)
    if end:
        q = q.filter(models.AttendanceEvent.event_ts <= end)
    return q.order_by(models.AttendanceEvent.event_ts.desc()).all()


@app.get("/api/v1/employees/{employee_code}/history", response_model=schemas.EmployeeHistoryResponse)
def get_employee_history(employee_code: str, db: Session = Depends(get_db)):
    """
    Aggregated view for the HR dashboard's employee detail drawer — distinct
    from GET /employees/{employee_code}/attendance above (which returns the
    raw event list used by the Employee dashboard). This endpoint adds
    manager lookup, face-enrollment status, and computed lifetime stats on
    top of a capped recent-history list.
    """
    employee = db.query(models.Employee).filter_by(employee_code=employee_code).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    manager_name = None
    if employee.manager_id:
        manager = db.query(models.Employee).filter_by(id=employee.manager_id).first()
        manager_name = manager.full_name if manager else None

    non_rejected = models.AttendanceEvent.status != models.EventStatus.REJECTED

    last_check_in_event = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.employee_id == employee.id,
            models.AttendanceEvent.event_type == models.EventType.CHECK_IN,
            non_rejected,
        )
        .order_by(models.AttendanceEvent.event_ts.desc())
        .first()
    )
    last_check_out_event = (
        db.query(models.AttendanceEvent)
        .filter(
            models.AttendanceEvent.employee_id == employee.id,
            models.AttendanceEvent.event_type == models.EventType.CHECK_OUT,
            non_rejected,
        )
        .order_by(models.AttendanceEvent.event_ts.desc())
        .first()
    )

    # "Days present"/"late days" are counted as distinct calendar dates with
    # a qualifying check-in — an employee who checks in twice in one day
    # (e.g. a corrected regularization alongside the original) still counts
    # as one present day, not two.
    present_dates = (
        db.query(func.date(models.AttendanceEvent.event_ts))
        .filter(
            models.AttendanceEvent.employee_id == employee.id,
            models.AttendanceEvent.event_type == models.EventType.CHECK_IN,
            non_rejected,
        )
        .distinct()
        .count()
    )
    late_dates = (
        db.query(func.date(models.AttendanceEvent.event_ts))
        .filter(
            models.AttendanceEvent.employee_id == employee.id,
            models.AttendanceEvent.event_type == models.EventType.CHECK_IN,
            models.AttendanceEvent.status == models.EventStatus.FLAGGED,
        )
        .distinct()
        .count()
    )

    recent_events = (
        db.query(models.AttendanceEvent)
        .filter(models.AttendanceEvent.employee_id == employee.id)
        .order_by(models.AttendanceEvent.event_ts.desc())
        .limit(50)
        .all()
    )

    return schemas.EmployeeHistoryResponse(
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department,
        manager_name=manager_name,
        face_enrolled=employee.face_descriptor is not None,
        last_check_in=last_check_in_event.event_ts if last_check_in_event else None,
        last_check_out=last_check_out_event.event_ts if last_check_out_event else None,
        total_days_present=present_dates,
        total_late_days=late_dates,
        history=[
            schemas.EmployeeHistoryEvent(event_ts=e.event_ts, event_type=e.event_type.value, status=e.status.value)
            for e in recent_events
        ],
    )


# ---------------------------------------------------------------------------
# IMPORTANT — ROUTE ORDERING: /api/v1/attendance/live and
# /api/v1/attendance/history are registered here, BEFORE
# GET /api/v1/attendance/{event_id} further down. This is required, not
# stylistic: FastAPI/Starlette matches path routes in registration order
# using plain string segment matching — the {event_id}: uuid.UUID type hint
# is only enforced by FastAPI's parameter validation AFTER a route already
# matched, not at the routing layer itself. If {event_id} were registered
# first, a request to /attendance/live would match it first (matching
# event_id="live") and fail with a 422 rather than ever reaching the
# handler below. This is the same class of bug documented in Phase 6's
# face-descriptors endpoint — verified again here with the same
# Starlette-route-matching test technique before shipping.
# ---------------------------------------------------------------------------

@app.get("/api/v1/attendance/live", response_model=List[schemas.LiveAttendanceItem])
def get_live_attendance(db: Session = Depends(get_db)):
    """Latest 20 attendance events, newest-submitted first (ordered by
    received_ts, not event_ts, so a backdated regularization correction
    doesn't jump the live feed — it shows up in history, not here)."""
    rows = (
        db.query(models.AttendanceEvent, models.Employee)
        .join(models.Employee, models.AttendanceEvent.employee_id == models.Employee.id)
        .order_by(models.AttendanceEvent.received_ts.desc())
        .limit(20)
        .all()
    )
    return [
        schemas.LiveAttendanceItem(
            id=event.id,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            event_type=event.event_type.value,
            event_ts=event.event_ts,
            status=event.status.value,
        )
        for event, employee in rows
    ]


@app.get("/api/v1/attendance/history", response_model=schemas.AttendanceHistoryResponse)
def get_attendance_history_table(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Matches employee_code or full_name, case-insensitive"),
    department: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_preset: Optional[str] = Query(None, alias="date", description="TODAY | YESTERDAY | THIS_WEEK | THIS_MONTH"),
    db: Session = Depends(get_db),
):
    q = db.query(models.AttendanceEvent, models.Employee).join(
        models.Employee, models.AttendanceEvent.employee_id == models.Employee.id
    )

    if search:
        like = f"%{search}%"
        q = q.filter(
            (models.Employee.employee_code.ilike(like)) | (models.Employee.full_name.ilike(like))
        )
    if department:
        q = q.filter(models.Employee.department == department)
    if status_filter:
        q = q.filter(models.AttendanceEvent.status == status_filter)
    if date_preset:
        try:
            start, end = dateranges.resolve_preset(date_preset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        q = q.filter(models.AttendanceEvent.event_ts >= start, models.AttendanceEvent.event_ts <= end)

    total = q.count()
    rows = (
        q.order_by(models.AttendanceEvent.event_ts.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    items = [
        schemas.AttendanceHistoryItem(
            id=event.id,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department=employee.department,
            event_ts=event.event_ts,
            event_type=event.event_type.value,
            status=event.status.value,
        )
        for event, employee in rows
    ]
    return schemas.AttendanceHistoryResponse(items=items, total=total, page=page, pageSize=pageSize)


@app.get("/api/v1/attendance/{event_id}", response_model=schemas.AttendanceEventResponse)
def get_attendance_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    event = db.query(models.AttendanceEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


# ---------------------------------------------------------------------------
# Internal — called only by regularization-service after manager approval.
# This is the single path by which a regularization can mutate the ledger.
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/internal/regularization-correction",
    response_model=schemas.AttendanceEventResponse,
    dependencies=[Depends(require_api_key)],
)
def apply_regularization_correction(payload: schemas.RegularizationCorrectionRequest, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter_by(employee_code=payload.employee_code, is_active=True).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Active employee not found")

    original_event = None
    if payload.original_event_id:
        original_event = (
            db.query(models.AttendanceEvent)
            .filter_by(id=payload.original_event_id, employee_id=employee.id)
            .first()
        )
        if not original_event:
            raise HTTPException(status_code=404, detail="original_event_id not found for this employee")

    event_ts = payload.event_ts
    if event_ts.tzinfo is None:
        event_ts = event_ts.replace(tzinfo=timezone.utc)

    # Manager-approved corrections are written as VALIDATED directly — they've
    # already been through the human review the deterministic engine exists
    # to triage employees *into*, so they don't get re-flagged.
    new_event = models.AttendanceEvent(
        employee_id=employee.id,
        device_id=None,
        event_type=payload.event_type,
        source=models.EventSource.REGULARIZATION,
        event_ts=event_ts,
        status=models.EventStatus.VALIDATED,
        validation_notes=f"Regularization approved by {payload.actor_id}: {payload.decision_notes or ''}".strip(),
    )
    db.add(new_event)
    db.flush()

    audit.write_audit_entry(
        db, entity_type="attendance_event", entity_id=new_event.id,
        actor_id=payload.actor_id, actor_role=payload.actor_role, action="REGULARIZE_CREATE",
        before_state=None,
        after_state={
            "employee_code": employee.employee_code,
            "event_type": payload.event_type,
            "event_ts": event_ts.isoformat(),
            "superseding_event_id": str(payload.original_event_id) if payload.original_event_id else None,
        },
    )

    if original_event:
        before = {"status": original_event.status.value, "superseded_by": None}
        original_event.status = models.EventStatus.SUPERSEDED
        original_event.superseded_by = new_event.id
        db.flush()
        audit.write_audit_entry(
            db, entity_type="attendance_event", entity_id=original_event.id,
            actor_id=payload.actor_id, actor_role=payload.actor_role, action="REGULARIZE_SUPERSEDE",
            before_state=before,
            after_state={"status": "SUPERSEDED", "superseded_by": str(new_event.id)},
        )

    db.commit()
    db.refresh(new_event)
    return new_event


@app.patch(
    "/api/v1/internal/attendance-events/{event_id}/status",
    response_model=schemas.AttendanceEventResponse,
    dependencies=[Depends(require_api_key)],
)
def update_event_status(event_id: uuid.UUID, payload: schemas.EventStatusUpdateRequest, db: Session = Depends(get_db)):
    """
    Internal endpoint — called by ai-agent-service after a human has resolved
    a review-queue item (e.g. confirming an anomaly flag as real fraud).
    This keeps attendance-service the single writer of ledger truth even for
    AI-agent-triggered corrections: the agent never touches the events table
    directly, it always goes through this API.
    """
    event = db.query(models.AttendanceEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        new_status = models.EventStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    before = {"status": event.status.value, "validation_notes": event.validation_notes}
    event.status = new_status
    event.validation_notes = payload.reason
    db.flush()

    audit.write_audit_entry(
        db, entity_type="attendance_event", entity_id=event.id,
        actor_id=payload.actor_id, actor_role=payload.actor_role, action="STATUS_UPDATE",
        before_state=before,
        after_state={"status": new_status.value, "reason": payload.reason},
    )
    db.commit()
    db.refresh(event)
    return event
