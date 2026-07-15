import enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Time, Text, Float, REAL,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.database import Base


class EventType(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class EventStatus(str, enum.Enum):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class AnomalyFlagType(str, enum.Enum):
    GEO_JUMP = "GEO_JUMP"
    SAME_DEVICE_MULTI_EMPLOYEE = "SAME_DEVICE_MULTI_EMPLOYEE"
    FREQUENCY_ANOMALY = "FREQUENCY_ANOMALY"
    SHIFT_WINDOW = "SHIFT_WINDOW"


class AnomalyFlagStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLEARED = "CLEARED"
    CONFIRMED = "CONFIRMED"


class ReviewPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class ReviewStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class RegularizationStatus(str, enum.Enum):
    PENDING = "PENDING"
    AI_PRESCREENED = "AI_PRESCREENED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


# ---- Read-only views of tables owned by other services ----

class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_code = Column(String(32))
    full_name = Column(String(255))
    department = Column(String(128))
    manager_id = Column(UUID(as_uuid=True))


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True)
    device_code = Column(String(64))
    latitude = Column(Float)
    longitude = Column(Float)


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"))
    event_type = Column(SAEnum(EventType, name="event_type"))
    source = Column(String(32))
    event_ts = Column(DateTime(timezone=True))
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(SAEnum(EventStatus, name="event_status"))


class RegularizationRequest(Base):
    __tablename__ = "regularization_requests"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    target_date = Column(Date)
    requested_event_type = Column(SAEnum(EventType, name="event_type"))
    requested_time = Column(Time)
    reason = Column(Text)
    status = Column(SAEnum(RegularizationStatus, name="regularization_status"))
    ai_recommendation = Column(Text)
    ai_confidence = Column(REAL)
    created_at = Column(DateTime(timezone=True))


# ---- Owned by this service ----

class AnomalyFlag(Base):
    __tablename__ = "anomaly_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attendance_event_id = Column(UUID(as_uuid=True), ForeignKey("attendance_events.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    flag_type = Column(SAEnum(AnomalyFlagType, name="anomaly_flag_type"), nullable=False)
    rule_score = Column(REAL, nullable=False)
    llm_narrative = Column(Text)
    llm_confidence = Column(REAL)
    status = Column(SAEnum(AnomalyFlagStatus, name="anomaly_flag_status"), nullable=False, default=AnomalyFlagStatus.OPEN)
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


class HumanReviewQueueItem(Base):
    __tablename__ = "human_review_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type = Column(String(32), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    priority = Column(SAEnum(ReviewPriority, name="review_priority"), nullable=False, default=ReviewPriority.NORMAL)
    reason = Column(Text, nullable=False)
    status = Column(SAEnum(ReviewStatus, name="review_status"), nullable=False, default=ReviewStatus.OPEN)
    resolution = Column(String(32))
    resolution_notes = Column(Text)
    resolved_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


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
