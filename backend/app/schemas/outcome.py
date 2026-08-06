"""Outcome I/O schemas (DATA_MODEL.md §2.8).

Append-only event log — Create + Out only; no Update schema.
``OutcomeOut`` deliberately omits ``user_id`` (implicit via auth scope).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import OutcomeEventType


class OutcomeCreate(BaseModel):
    generated_email_id: int
    event_type: OutcomeEventType


class OutcomeOut(BaseModel):
    id: int
    generated_email_id: int
    event_type: OutcomeEventType
    occurred_at: datetime
    model_config = ConfigDict(from_attributes=True)
