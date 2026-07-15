import enum
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    HR_ADMIN = "HR_ADMIN"
    PAYROLL = "PAYROLL"
    SYSTEM_AGENT = "SYSTEM_AGENT"
    SUPER_ADMIN = "SUPER_ADMIN"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Employee(Base):
    """Minimal read-only view of the employee record this service needs."""
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True)
    employee_code = Column(String(32))
    full_name = Column(String(255))
    manager_id = Column(UUID(as_uuid=True))
