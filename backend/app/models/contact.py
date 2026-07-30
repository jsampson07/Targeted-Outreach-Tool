from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import VerificationTier, verification_tier_enum
from app.db.base import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), index=True, nullable=False
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    best_verification_tier: Mapped[VerificationTier] = mapped_column(
        verification_tier_enum, nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
