"""Outcome I/O schemas (DATA_MODEL.md §2.8).

Append-only event log — Create + Out only; no Update schema.
Retraction is a separate one-way action (``POST …/retract``), not a
general PATCH/Update: it flips ``voided`` false→true and nothing else.
``OutcomeOut`` omits ``user_id`` (implicit via auth scope) but includes
``voided`` so the retract response can confirm the resulting state.
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
    voided: bool
    model_config = ConfigDict(from_attributes=True)
