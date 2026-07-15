import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GenerateReportRequest(BaseModel):
    period_type: str = Field(..., pattern="^(DAILY|WEEKLY|MONTHLY|ADHOC)$")
    reference_time: Optional[datetime] = None  # defaults to now; lets you generate a report "as of" a past moment


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_id: str
    channel: str
    recipient: str
    report_period: str
    period_start: datetime
    period_end: datetime
    payload_summary: str
    whatsapp_message_id: Optional[str]
    status: str
    attempt_count: int
    last_error: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
