import enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Float, Time,
    ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.database import Base


class EventType(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class EventSource(str, enum.Enum):
    BIOMETRIC = "BIOMETRIC"
    MOBILE = "MOBILE"
    WEB = "WEB"
    REGULARIZATION = "REGULARIZATION"


class EventStatus(str, enum.Enum):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_code = Column(String(32), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    department = Column(String(128))
    manager_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    shift_start = Column(Time, nullable=False)
    shift_end = Column(Time, nullable=False)
    grace_minutes = Column(Integer, nullable=False, default=10)
    geofence_lat = Column(Float)
    geofence_lng = Column(Float)
    geofence_radius_m = Column(Integer, default=200)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    face_descriptor = Column(JSONB)  # 128-dim float array from face-api.js recognition model; null until enrolled
    face_enrolled_at = Column(DateTime(timezone=True))

class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code = Column(String(64), unique=True, nullable=False)
    location_name = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    is_active = Column(Boolean, nullable=False, default=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"))
    event_type = Column(SAEnum(EventType, name="event_type"), nullable=False)
    source = Column(SAEnum(EventSource, name="event_source"), nullable=False)
    event_ts = Column(DateTime(timezone=True), nullable=False)
    received_ts = Column(DateTime(timezone=True), server_default=func.now())
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(SAEnum(EventStatus, name="event_status"), nullable=False, default=EventStatus.PENDING_VALIDATION)
    validation_notes = Column(Text)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("attendance_events.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    actor_id = Column(String(128), nullable=False)
    actor_role = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    before_state = Column(JSONB)
    after_state = Column(JSONB)
    prev_hash = Column(String(64))
    record_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RegularizationRequest(Base):
    """
    Read-only view of a table owned by regularization-service. Same
    shared-DB, per-service-bounded-context pattern used elsewhere in this
    project (e.g. reporting-service and ai-agent-service both have their own
    read-only view of this same table) — attendance-service never writes to
    it, only reads it here to compute the dashboard's pendingRegularization
    count.
    """
    __tablename__ = "regularization_requests"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    status = Column(String(32))
    created_at = Column(DateTime(timezone=True))
