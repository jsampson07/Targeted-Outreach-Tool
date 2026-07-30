from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OutcomeEventType, outcome_event_type_enum
from app.db.base import Base


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_email_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generated_emails.id"), index=True, nullable=False
    )
    event_type: Mapped[OutcomeEventType] = mapped_column(
        outcome_event_type_enum, nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
