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


class RegularizationStatus(str, enum.Enum):
    PENDING = "PENDING"
    AI_PRESCREENED = "AI_PRESCREENED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    HR_ADMIN = "HR_ADMIN"
    PAYROLL = "PAYROLL"
    SYSTEM_AGENT = "SYSTEM_AGENT"
    SUPER_ADMIN = "SUPER_ADMIN"


# ---- Read-mostly views of tables owned by other services' bounded contexts ----
# (Shared Postgres instance per the design doc's data layer; attendance-service
#  remains the only writer of attendance_events, identity-service the only
#  writer of users — this service only ever reads those two.)

class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_code = Column(String(32))
    full_name = Column(String(255))
    manager_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    is_active = Column(Boolean)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)
    username = Column(String(64))
    role = Column(SAEnum(UserRole, name="user_role"))
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    event_type = Column(SAEnum(EventType, name="event_type"))
    status = Column(SAEnum(EventStatus, name="event_status"))


# ---- Owned by this service ----

class RegularizationRequest(Base):
    __tablename__ = "regularization_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    target_date = Column(Date, nullable=False)
    requested_event_type = Column(SAEnum(EventType, name="event_type"), nullable=False)
    requested_time = Column(Time, nullable=False)
    reason = Column(Text, nullable=False)
    original_event_id = Column(UUID(as_uuid=True), ForeignKey("attendance_events.id"))
    new_event_id = Column(UUID(as_uuid=True), ForeignKey("attendance_events.id"))
    status = Column(SAEnum(RegularizationStatus, name="regularization_status"), nullable=False, default=RegularizationStatus.PENDING)
    ai_recommendation = Column(Text)
    ai_confidence = Column(REAL)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    decision_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True))


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
