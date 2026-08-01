"""Tiered contact discovery orchestrator.

Owns caching, DISCOVERY_TIERS sequencing, reconciliation, and
user-facing fallback copy. Providers only answer one search() call
apiece (ARCHITECTURE.md §4.2 / §4.3 / §5 / §6).
"""

from sqlalchemy.orm import Session

from app.core.enums import VerificationTier
from app.models.company import Company
from app.models.contact import Contact
from app.models.raw_provider_result import RawProviderResult
from app.providers.base import ContactProvider, ProviderCandidate, ProviderStatus
from app.schemas.contact import (
    ConfidenceBreakdown,
    ContactDiscoveryResponse,
    ContactOut,
)

DISCOVERY_TIERS: list[tuple[str, list[str]]] = [
    (
        "recruiter",
        [
            "recruiter",
            "technical recruiter",
            "university recruiter",
            "campus recruiter",
        ],
    ),
    (
        "talent_acquisition",
        [
            "talent acquisition",
            "people operations",
            "hr business partner",
            "hr generalist",
        ],
    ),
    (
        "hiring_manager",
        [
            "hiring manager",
            "engineering manager",
            "director of engineering",
        ],
    ),
    (
        "founder",
        ["founder", "co-founder", "ceo", "cto"],
    ),
]

# Higher rank wins on name-collision resolution (v1 stub).
_VERIFICATION_TIER_RANK = {
    VerificationTier.VERIFIED: 3,
    VerificationTier.PATTERN_GUESSED: 2,
    VerificationTier.CATCH_ALL: 1,
    VerificationTier.UNKNOWN: 0,
}

# Unvalidated v1 calibration guess — see _compute_confidence.
_VERIFICATION_TIER_SCORES = {
    VerificationTier.VERIFIED: 1.0,
    VerificationTier.PATTERN_GUESSED: 0.7,
    VerificationTier.CATCH_ALL: 0.4,
    VerificationTier.UNKNOWN: 0.1,
}
_EMPLOYMENT_SIGNAL_SCORES = {
    "current": 1.0,
    "unknown": 0.5,
    "stale": 0.0,
}

_TIER_DISPLAY = {
    "recruiter": "recruiter",
    "talent_acquisition": "talent acquisition",
    "hiring_manager": "hiring manager",
    "founder": "founder/executive",
}

_EXHAUSTED_FALLBACK = (
    "No contact could be found for this company across any tier."
)


def get_or_create_company(db: Session, domain: str) -> Company:
    """Lookup Company by domain; create a stub row if missing.

    Placeholder name is derived naively from the domain string. This is a
    stub superseded by the future company-name-resolution endpoint
    (ARCHITECTURE.md §7 / DATA_MODEL.md §2.4.1), which will supply a real
    name before discovery runs.
    """
    existing = db.query(Company).filter(Company.domain == domain).first()
    if existing is not None:
        return existing

    # e.g. "acme-corp.com" -> "Acme Corp"
    label = domain.split(".")[0].replace("-", " ").replace("_", " ").strip()
    name = label.title() if label else domain

    company = Company(name=name, domain=domain)
    db.add(company)
    db.flush()
    return company


def _compute_confidence(
    verification_tier: VerificationTier,
    *,
    cross_provider_corroboration: bool,
    employment_currency_signal: str,
    domain_check_passed: bool,
    name_collision_detected: bool,
) -> tuple[float, ConfidenceBreakdown]:
    """Weighted confidence score + breakdown.

    Unvalidated v1 calibration guess — weights and per-signal scores are
    placeholders pending real reconciliation data (OPEN_QUESTIONS.md).
    Do not treat the numeric output as a tuned production signal.
    """
    verification_tier_score = _VERIFICATION_TIER_SCORES[verification_tier]
    breakdown = ConfidenceBreakdown(
        verification_tier_score=verification_tier_score,
        cross_provider_corroboration=cross_provider_corroboration,
        employment_currency_signal=employment_currency_signal,
        domain_check_passed=domain_check_passed,
        name_collision_detected=name_collision_detected,
    )
    score = (
        0.50 * verification_tier_score
        + 0.20 * (1.0 if cross_provider_corroboration else 0.0)
        + 0.15 * _EMPLOYMENT_SIGNAL_SCORES[employment_currency_signal]
        + 0.15 * (1.0 if domain_check_passed else 0.0)
    )
    if name_collision_detected:
        score *= 0.85
    return score, breakdown


def _resolve_collision(
    candidates: list[ProviderCandidate],
) -> tuple[ProviderCandidate, bool]:
    """Pick one candidate when a tier returns multiple people.

    v1 stub: highest verification_tier wins, first-returned as tiebreak.
    Detection is real; revisit resolution once real multi-candidate
    collisions are observed (OPEN_QUESTIONS.md).
    """
    if len(candidates) <= 1:
        return candidates[0], False

    # max() keeps the first element among equal keys — first-returned tiebreak.
    winner = max(
        candidates,
        key=lambda c: _VERIFICATION_TIER_RANK[c.verification_tier],
    )
    return winner, True


def _build_fallback_reason(
    tier_used: str,
    skipped: list[tuple[str, str]],
) -> str | None:
    """Plain-language reason for falling past earlier tiers (§6).

    Prefer "temporarily unavailable" phrasing over "not found" if any
    skipped tier was provider_unavailable.
    """
    if not skipped:
        return None

    any_unavailable = any(reason == "provider_unavailable" for _, reason in skipped)
    display = _TIER_DISPLAY.get(tier_used, tier_used)

    if any_unavailable:
        return (
            f"Earlier contact tiers were temporarily unavailable; "
            f"showing a {display} contact instead."
        )

    skipped_labels = [
        _TIER_DISPLAY.get(name, name) for name, _ in skipped
    ]
    if len(skipped_labels) == 1:
        earlier = skipped_labels[0]
    elif len(skipped_labels) == 2:
        earlier = f"{skipped_labels[0]} or {skipped_labels[1]}"
    else:
        earlier = ", ".join(skipped_labels[:-1]) + f", or {skipped_labels[-1]}"

    return (
        f"No {earlier} contact found; showing a {display} contact instead."
    )


def _persist_raw_results(
    db: Session,
    company_id: int,
    provider_name: str,
    candidates: list[ProviderCandidate],
    queried_titles: list[str],
) -> None:
    for candidate in candidates:
        raw_response = {
            **candidate.raw_response,
            "queried_titles": queried_titles,
        }
        db.add(
            RawProviderResult(
                company_id=company_id,
                provider_name=provider_name,
                candidate_name=candidate.name,
                candidate_title=candidate.title,
                candidate_email=candidate.email,
                verification_tier=candidate.verification_tier,
                raw_response=raw_response,
            )
        )


async def discover_contact(
    db: Session,
    providers: list[ContactProvider],
    company_domain: str,
    role_title: str,
) -> ContactDiscoveryResponse:
    """Run the tiered discovery pipeline for one company domain.

    ``role_title`` is accepted for API symmetry but unused by discovery for
    now — all four tiers search fixed title lists (OPEN_QUESTIONS.md).
    """
    _ = role_title  # reserved; tiering ignores role-specific titles in v1

    company = get_or_create_company(db, company_domain)

    existing = (
        db.query(Contact).filter(Contact.company_id == company.id).first()
    )
    if (
        existing is not None
        and existing.best_verification_tier != VerificationTier.UNKNOWN
    ):
        return ContactDiscoveryResponse(
            contact=ContactOut.model_validate(existing),
            fallback_reason=None,
            tier_used=None,
        )

    skipped: list[tuple[str, str]] = []

    for tier_name, titles in DISCOVERY_TIERS:
        # Collect (provider_name, candidates) across every provider at this
        # tier — loop even when len(providers)==1 so Phase 2 only extends
        # the list, without rewriting the loop.
        hit_candidates: list[ProviderCandidate] = []
        hit_by_provider: list[tuple[str, list[ProviderCandidate]]] = []
        saw_unavailable = False
        saw_success_empty = False

        for provider in providers:
            result = await provider.search(company_domain, titles)
            if (
                result.status == ProviderStatus.SUCCESS
                and len(result.candidates) > 0
            ):
                hit_candidates.extend(result.candidates)
                hit_by_provider.append((provider.name, list(result.candidates)))
            elif result.status == ProviderStatus.SUCCESS:
                saw_success_empty = True
            else:
                # RATE_LIMITED or ERROR — distinct from empty SUCCESS.
                saw_unavailable = True

        if hit_candidates:
            for provider_name, candidates in hit_by_provider:
                _persist_raw_results(
                    db, company.id, provider_name, candidates, titles
                )

            selected, name_collision_detected = _resolve_collision(
                hit_candidates
            )

            domain_check_passed = (
                selected.email is not None
                and selected.email.split("@")[-1].lower()
                == company_domain.lower()
            )
            # Structurally impossible with a single provider; keep the field
            # real so Phase 2 only has to implement the check.
            cross_provider_corroboration = False
            # Hardcoded "unknown": Hunter's last_seen_on / verification.date are
            # email-source / deliverability dates, not employment currency
            # (OPEN_QUESTIONS.md Resolved).
            employment_currency_signal = "unknown"

            confidence_score, breakdown = _compute_confidence(
                selected.verification_tier,
                cross_provider_corroboration=cross_provider_corroboration,
                employment_currency_signal=employment_currency_signal,
                domain_check_passed=domain_check_passed,
                name_collision_detected=name_collision_detected,
            )

            contact = Contact(
                company_id=company.id,
                name=selected.name,
                title=selected.title,
                email=selected.email,
                best_verification_tier=selected.verification_tier,
                confidence_score=confidence_score,
                confidence_breakdown=breakdown.model_dump(),
            )
            db.add(contact)
            db.commit()
            db.refresh(contact)

            fallback_reason = _build_fallback_reason(tier_name, skipped)
            return ContactDiscoveryResponse(
                contact=ContactOut.model_validate(contact),
                fallback_reason=fallback_reason,
                tier_used=tier_name,
            )

        # No successful non-empty result this tier — record why, keep distinct.
        if saw_unavailable:
            skipped.append((tier_name, "provider_unavailable"))
        elif saw_success_empty:
            skipped.append((tier_name, "no_match"))

    # Company stub (if newly created) should still persist for reuse; no Contact.
    db.commit()
    return ContactDiscoveryResponse(
        contact=None,
        fallback_reason=_EXHAUSTED_FALLBACK,
        tier_used=None,
    )
