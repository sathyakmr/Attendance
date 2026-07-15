import uuid
from datetime import date, time, datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict


class RegularizationCreateRequest(BaseModel):
    target_date: date
    requested_event_type: Literal["CHECK_IN", "CHECK_OUT"]
    requested_time: time
    reason: str
    original_event_id: Optional[uuid.UUID] = None


class RegularizationDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT", "ESCALATE"]
    notes: Optional[str] = None


class RegularizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    target_date: date
    requested_event_type: str
    requested_time: time
    reason: str
    original_event_id: Optional[uuid.UUID]
    new_event_id: Optional[uuid.UUID]
    status: str
    decided_by: Optional[uuid.UUID]
    decision_notes: Optional[str]
    created_at: datetime
    decided_at: Optional[datetime]
