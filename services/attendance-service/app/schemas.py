import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class CheckInRequest(BaseModel):
    employee_code: str = Field(..., examples=["EMP001"])
    device_code: Optional[str] = Field(None, description="Required for BIOMETRIC source")
    event_type: str = Field(..., pattern="^(CHECK_IN|CHECK_OUT)$")
    source: str = Field(..., pattern="^(BIOMETRIC|MOBILE|WEB)$")
    event_ts: Optional[datetime] = Field(None, description="Defaults to server time if omitted")
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AttendanceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    device_id: Optional[uuid.UUID]
    event_type: str
    source: str
    event_ts: datetime
    status: str
    validation_notes: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime


class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    department: Optional[str] = None
    shift_start: str = "09:00:00"
    shift_end: str = "18:00:00"
    grace_minutes: int = 10
    geofence_lat: Optional[float] = None
    geofence_lng: Optional[float] = None
    geofence_radius_m: int = 200


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_code: str
    full_name: str
    department: Optional[str]
    manager_id: Optional[uuid.UUID]
    is_active: bool
    created_at: datetime


class RegularizationCorrectionRequest(BaseModel):
    """
    Internal, service-to-service contract. Called only by the regularization
    service after a manager has approved a request — this endpoint is the
    one and only path by which a regularization can mutate the ledger,
    keeping attendance-service the single writer of ledger truth.
    """
    employee_code: str
    event_type: str = Field(..., pattern="^(CHECK_IN|CHECK_OUT)$")
    event_ts: datetime
    original_event_id: Optional[uuid.UUID] = None
    actor_id: str = Field(..., description="user id of the approving manager")
    actor_role: str = Field(..., description="role of the approving manager")
    decision_notes: Optional[str] = None


class EventStatusUpdateRequest(BaseModel):
    """
    Internal, service-to-service contract. Called only by ai-agent-service
    after a human has resolved a review-queue item — the single path by
    which an anomaly-confirmed event status change reaches the ledger.
    """
    status: str = Field(..., pattern="^(VALIDATED|FLAGGED|REJECTED)$")
    actor_id: str
    actor_role: str
    reason: Optional[str] = None


class FaceEnrollRequest(BaseModel):
    descriptor: list[float] = Field(..., min_length=128, max_length=128)


class FaceDescriptorEntry(BaseModel):
    id: uuid.UUID
    employee_code: str
    full_name: str
    descriptor: list[float]


class DashboardSummaryResponse(BaseModel):
    totalEmployees: int
    presentToday: int
    absentToday: int
    lateToday: int
    faceEnrolled: int
    pendingRegularization: int


class LiveAttendanceItem(BaseModel):
    id: uuid.UUID
    employee_code: str
    full_name: str
    event_type: str
    event_ts: datetime
    status: str


class AttendanceHistoryItem(BaseModel):
    id: uuid.UUID
    employee_code: str
    full_name: str
    department: Optional[str]
    event_ts: datetime
    event_type: str
    status: str


class AttendanceHistoryResponse(BaseModel):
    items: list[AttendanceHistoryItem]
    total: int
    page: int
    pageSize: int


class EmployeeHistoryEvent(BaseModel):
    event_ts: datetime
    event_type: str
    status: str


class EmployeeHistoryResponse(BaseModel):
    employee_code: str
    full_name: str
    department: Optional[str]
    manager_name: Optional[str]
    face_enrolled: bool
    last_check_in: Optional[datetime]
    last_check_out: Optional[datetime]
    total_days_present: int
    total_late_days: int
    history: list[EmployeeHistoryEvent]
