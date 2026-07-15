import enum
import uuid

from sqlalchemy import (
    Column, String, DateTime, Integer, Text, Float,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.database import Base


class NotificationChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    FALLBACK_LOG = "FALLBACK_LOG"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class ReportPeriod(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    ADHOC = "ADHOC"


# ---- Owned by this service ----

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(String(64), unique=True, nullable=False)
    channel = Column(SAEnum(NotificationChannel, name="notification_channel"), nullable=False, default=NotificationChannel.WHATSAPP)
    recipient = Column(String(64), nullable=False)
    report_period = Column(SAEnum(ReportPeriod, name="report_period"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    payload_summary = Column(Text, nullable=False)
    whatsapp_message_id = Column(String(128))
    status = Column(SAEnum(NotificationStatus, name="notification_status"), nullable=False, default=NotificationStatus.PENDING)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    read_at = Column(DateTime(timezone=True))


# ---- Read-only views of tables owned by other services ----

class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_code = Column(String(32))
    full_name = Column(String(255))
    department = Column(String(128))


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"))
    event_type = Column(String(16))
    status = Column(String(32))
    event_ts = Column(DateTime(timezone=True))


class AnomalyFlag(Base):
    __tablename__ = "anomaly_flags"

    id = Column(UUID(as_uuid=True), primary_key=True)
    status = Column(String(16))
    created_at = Column(DateTime(timezone=True))


class RegularizationRequest(Base):
    __tablename__ = "regularization_requests"

    id = Column(UUID(as_uuid=True), primary_key=True)
    status = Column(String(32))
    created_at = Column(DateTime(timezone=True))


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
