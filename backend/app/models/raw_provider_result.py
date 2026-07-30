from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import VerificationTier, verification_tier_enum
from app.db.base import Base


class RawProviderResult(Base):
    __tablename__ = "raw_provider_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), index=True, nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    candidate_name: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_title: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_tier: Mapped[VerificationTier] = mapped_column(
        verification_tier_enum, nullable=False
    )
    raw_response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    queried_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
