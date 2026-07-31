"""Unit tests for contact_discovery service against real Postgres.

No HTTP layer — services are unit-tested directly (ARCHITECTURE.md §2).
Uses conftest db_session (transaction-rollback), not sqlite.
"""

import asyncio

from sqlalchemy.orm import Session

from app.core.enums import VerificationTier
from app.models.company import Company
from app.models.contact import Contact
from app.providers.base import (
    ProviderCandidate,
    ProviderSearchResult,
    ProviderStatus,
)
from app.providers.mock import MockProvider
from app.services import contact_discovery as discovery


def _candidate(
    *,
    name: str = "Alex Recruiter",
    title: str = "Recruiter",
    email: str = "alex@acme.com",
    tier: VerificationTier = VerificationTier.VERIFIED,
) -> ProviderCandidate:
    return ProviderCandidate(
        name=name,
        title=title,
        email=email,
        verification_tier=tier,
        raw_response={"source": "test"},
    )


def _success(*candidates: ProviderCandidate) -> ProviderSearchResult:
    return ProviderSearchResult(
        provider_name="mock",
        status=ProviderStatus.SUCCESS,
        candidates=list(candidates),
    )


def _empty() -> ProviderSearchResult:
    return ProviderSearchResult(
        provider_name="mock",
        status=ProviderStatus.SUCCESS,
        candidates=[],
    )


def _rate_limited() -> ProviderSearchResult:
    return ProviderSearchResult(
        provider_name="mock",
        status=ProviderStatus.RATE_LIMITED,
        candidates=[],
        error_message="rate limited",
    )


class _CountingMockProvider(MockProvider):
    """Spy that counts search() calls for cache-hit assertions."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.search_calls = 0

    async def search(self, company_domain: str, role_titles: list[str]):
        self.search_calls += 1
        return await super().search(company_domain, role_titles)


def test_tier1_hit_no_fallback(db_session: Session):
    provider = MockProvider(
        scripted={"acme.com": [_success(_candidate())]}
    )
    result = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "acme.com", "Software Engineer"
        )
    )

    assert result.tier_used == "recruiter"
    assert result.fallback_reason is None
    assert result.contact is not None
    assert result.contact.email == "alex@acme.com"
    assert result.contact.best_verification_tier == VerificationTier.VERIFIED


def test_empty_tiers_then_hiring_manager_hit(db_session: Session):
    # Call order: recruiter, talent_acquisition, hiring_manager, founder
    provider = MockProvider(
        scripted={
            "acme.com": [
                _empty(),
                _empty(),
                _success(
                    _candidate(
                        name="Sam Manager",
                        title="Engineering Manager",
                        email="sam@acme.com",
                    )
                ),
            ]
        }
    )
    result = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "acme.com", "Software Engineer"
        )
    )

    assert result.tier_used == "hiring_manager"
    assert result.contact is not None
    assert result.fallback_reason is not None
    reason = result.fallback_reason.lower()
    assert "not found" in reason or reason.startswith("no ")
    assert "temporarily unavailable" not in reason
    assert "hiring manager" in reason


def test_rate_limited_tier1_then_talent_acquisition_hit(db_session: Session):
    provider = MockProvider(
        scripted={
            "acme.com": [
                _rate_limited(),
                _success(
                    _candidate(
                        name="Pat TA",
                        title="Talent Acquisition",
                        email="pat@acme.com",
                    )
                ),
            ]
        }
    )
    result = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "acme.com", "Software Engineer"
        )
    )

    assert result.tier_used == "talent_acquisition"
    assert result.fallback_reason is not None
    assert "temporarily unavailable" in result.fallback_reason.lower()
    assert "not found" not in result.fallback_reason.lower()


def test_cache_hit_skips_providers(db_session: Session):
    company = Company(name="Cached Co", domain="cached.com")
    db_session.add(company)
    db_session.flush()
    db_session.add(
        Contact(
            company_id=company.id,
            name="Cached Person",
            title="Recruiter",
            email="cached@cached.com",
            best_verification_tier=VerificationTier.VERIFIED,
            confidence_score=0.8,
            confidence_breakdown={
                "verification_tier_score": 1.0,
                "cross_provider_corroboration": False,
                "employment_currency_signal": "unknown",
                "domain_check_passed": True,
                "name_collision_detected": False,
            },
        )
    )
    db_session.flush()

    provider = _CountingMockProvider(
        scripted={"cached.com": [_success(_candidate(email="x@cached.com"))]}
    )
    result = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "cached.com", "Engineer"
        )
    )

    assert provider.search_calls == 0
    assert result.tier_used is None
    assert result.fallback_reason is None
    assert result.contact is not None
    assert result.contact.email == "cached@cached.com"


def test_all_tiers_exhausted_no_contact_row(db_session: Session):
    provider = MockProvider(
        scripted={
            "empty.co": [_empty(), _empty(), _empty(), _empty()],
        }
    )
    result = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "empty.co", "Engineer"
        )
    )

    assert result.contact is None
    assert result.tier_used is None
    assert result.fallback_reason == (
        "No contact could be found for this company across any tier."
    )
    assert db_session.query(Contact).count() == 0
    # Company stub is still created for reuse.
    assert (
        db_session.query(Company).filter(Company.domain == "empty.co").count()
        == 1
    )


def test_name_collision_picks_higher_verification_tier(db_session: Session):
    lower = _candidate(
        name="Lower Tier",
        email="lower@acme.com",
        tier=VerificationTier.PATTERN_GUESSED,
    )
    higher = _candidate(
        name="Higher Tier",
        email="higher@acme.com",
        tier=VerificationTier.VERIFIED,
    )
    # Higher-tier candidate returned second — still should win on tier rank.
    provider = MockProvider(scripted={"acme.com": [_success(lower, higher)]})
    result = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "acme.com", "Engineer"
        )
    )

    assert result.contact is not None
    assert result.contact.name == "Higher Tier"
    assert result.contact.email == "higher@acme.com"
    assert result.contact.confidence_breakdown.name_collision_detected is True


def test_domain_mismatch_penalizes_confidence(db_session: Session):
    mismatch_provider = MockProvider(
        scripted={
            "acme.com": [
                _success(
                    _candidate(
                        name="Wrong Domain",
                        email="wrong@other.com",
                        tier=VerificationTier.VERIFIED,
                    )
                )
            ]
        }
    )
    mismatch = asyncio.run(
        discovery.discover_contact(
            db_session, [mismatch_provider], "acme.com", "Engineer"
        )
    )

    match_provider = MockProvider(
        scripted={
            "beta.com": [
                _success(
                    _candidate(
                        name="Right Domain",
                        email="right@beta.com",
                        tier=VerificationTier.VERIFIED,
                    )
                )
            ]
        }
    )
    match = asyncio.run(
        discovery.discover_contact(
            db_session, [match_provider], "beta.com", "Engineer"
        )
    )

    assert mismatch.contact is not None
    assert match.contact is not None
    assert mismatch.contact.confidence_breakdown.domain_check_passed is False
    assert match.contact.confidence_breakdown.domain_check_passed is True
    assert mismatch.contact.confidence_score < match.contact.confidence_score


def test_second_discovery_does_not_duplicate_company(db_session: Session):
    provider = MockProvider(
        scripted={
            "once.com": [
                _success(_candidate(email="a@once.com")),
            ]
        }
    )
    first = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "once.com", "Engineer"
        )
    )
    second = asyncio.run(
        discovery.discover_contact(
            db_session, [provider], "once.com", "Engineer"
        )
    )

    assert first.contact is not None
    assert second.contact is not None
    assert second.tier_used is None  # cache hit
    assert (
        db_session.query(Company).filter(Company.domain == "once.com").count()
        == 1
    )
