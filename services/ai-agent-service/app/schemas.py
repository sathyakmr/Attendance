import uuid
from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeEventRequest(BaseModel):
    event_id: uuid.UUID


class AnomalyFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attendance_event_id: uuid.UUID
    employee_id: uuid.UUID
    flag_type: str
    rule_score: float
    llm_narrative: Optional[str]
    llm_confidence: Optional[float]
    status: str
    details: Optional[dict]
    created_at: datetime


class AnalyzeEventResponse(BaseModel):
    event_id: uuid.UUID
    flags_created: List[AnomalyFlagResponse]
    routed_to_review: bool


class PrescreenRequest(BaseModel):
    request_id: uuid.UUID
    employee_id: uuid.UUID
    employee_code: str
    target_date: date
    requested_event_type: str
    requested_time: str
    reason: str


class PrescreenResponse(BaseModel):
    recommendation: str
    confidence: float
    risk_level: str
    source: str  # "LLM" | "DETERMINISTIC" — transparency about which path produced this


class NLQueryRequest(BaseModel):
    question: str = Field(..., max_length=1000)


class NLQueryResponse(BaseModel):
    answer: str
    metric: Optional[str]
    result_count: Optional[int]
    grounded: bool
    source: str  # "LLM_INTENT" | "DETERMINISTIC_PARSE" | "REJECTED"


class ReviewQueueItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    employee_id: Optional[uuid.UUID]
    priority: str
    reason: str
    status: str
    resolution: Optional[str]
    resolution_notes: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]


class ResolveReviewRequest(BaseModel):
    resolution: str = Field(..., pattern="^(CONFIRMED|DISMISSED)$")
    notes: Optional[str] = None
