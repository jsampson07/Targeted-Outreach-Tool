"""Dev-only scripted results for MockProvider when CONTACT_PROVIDER=mock.

Wired by the contact-discovery router factory (`_build_providers`). Unit
tests build their own MockProvider(scripted=…) and do not import this.

Domains are intentionally fictional — enter them via FRAME 1's manual
domain fallback (Clearbit may not suggest them). See ARCHITECTURE.md §4.5.
"""

from app.core.enums import VerificationTier
from app.providers.base import (
    ProviderCandidate,
    ProviderSearchResult,
    ProviderStatus,
)


def _candidate(
    *,
    name: str,
    title: str,
    email: str,
    tier: VerificationTier,
) -> ProviderCandidate:
    return ProviderCandidate(
        name=name,
        title=title,
        email=email,
        verification_tier=tier,
        raw_response={"source": "dev_fixture"},
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


# Queue length = one entry per DISCOVERY_TIERS call (up to 4). Discovery
# stops at the first non-empty SUCCESS, so trailing empties are unused
# for hit scenarios but keep the script honest for exhausted runs.
DEV_SCRIPTED_RESULTS: dict[str, list[ProviderSearchResult]] = {
    # Tier-1 verified recruiter — no fallback_reason.
    "acme.com": [
        _success(
            _candidate(
                name="Alex Recruiter",
                title="Technical Recruiter",
                email="alex@acme.com",
                tier=VerificationTier.VERIFIED,
            )
        ),
    ],
    # Empty recruiter + TA, then pattern-guessed hiring manager —
    # exercises fallback_reason + lower verification confidence.
    "globex.com": [
        _empty(),
        _empty(),
        _success(
            _candidate(
                name="Sam Manager",
                title="Engineering Manager",
                email="sam@globex.com",
                tier=VerificationTier.PATTERN_GUESSED,
            )
        ),
    ],
    # All tiers empty — contact null + exhausted fallback_reason.
    "empty.co": [
        _empty(),
        _empty(),
        _empty(),
        _empty(),
    ],
}
