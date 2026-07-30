from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeneratedEmail(Base):
    __tablename__ = "generated_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id"), index=True, nullable=False
    )
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id"), index=True, nullable=False
    )
    job_description_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_descriptions.id"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    eval_score: Mapped[float] = mapped_column(Float, nullable=False)
    eval_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    match_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    gate_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
