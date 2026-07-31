"""Contact and discovery I/O schemas (DATA_MODEL.md §2.4 / §2.6 / §2.6.1)."""

from pydantic import BaseModel, ConfigDict

from app.core.enums import VerificationTier


class ContactDiscoveryRequest(BaseModel):
    company_domain: str
    role_title: str


class ConfidenceBreakdown(BaseModel):
    verification_tier_score: float
    cross_provider_corroboration: bool
    employment_currency_signal: str  # "current" | "stale" | "unknown"
    domain_check_passed: bool
    name_collision_detected: bool


class ContactOut(BaseModel):
    id: int
    company_id: int
    name: str | None
    title: str | None
    email: str | None
    best_verification_tier: VerificationTier
    confidence_score: float
    confidence_breakdown: ConfidenceBreakdown
    model_config = ConfigDict(from_attributes=True)


class ContactDiscoveryResponse(BaseModel):
    contact: ContactOut | None
    fallback_reason: str | None
    tier_used: str | None
