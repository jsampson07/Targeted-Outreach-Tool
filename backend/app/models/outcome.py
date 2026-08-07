from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OutcomeEventType, outcome_event_type_enum
from app.db.base import Base


class Outcome(Base):
    __tablename__ = "outcomes"
    __table_args__ = (
        # At most one non-voided SENT per generated_email_id. Voided SENT
        # rows are excluded so retract → re-mark Sent is a fresh insert.
        # Migration: e8a3c71f2049. See DATA_MODEL.md §2.8.
        Index(
            "uq_outcomes_generated_email_id_nonvoided_sent",
            "generated_email_id",
            unique=True,
            postgresql_where=text("voided = false AND event_type = 'sent'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=False
    )
    generated_email_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generated_emails.id"), index=True, nullable=False
    )
    event_type: Mapped[OutcomeEventType] = mapped_column(
        outcome_event_type_enum, nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Soft-delete flag for mistaken logs. One-way (false→true only). No
    # standalone index: list/analytics filter via already-indexed user_id,
    # and a boolean alone is too low-selectivity to earn its own index.
    voided: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
