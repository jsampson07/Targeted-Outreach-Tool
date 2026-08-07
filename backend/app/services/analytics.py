"""Reply-rate analytics — pure aggregation + thin DB orchestration.

Mirrors the ``eval.py`` / ``matching.py`` precedent: a pure compute function
(unit-testable with no DB/HTTP) and a thin wrapper that loads data via the
entity-owning services then delegates.

CRITICAL DISCIPLINE:
- OUTCOMES reads go through ``outcomes.list_outcomes`` only — never query
  ``Outcome`` here (voided filter lives in that module).
- GENERATED_EMAILS / Contact reads go through
  ``generated_emails.list_generated_emails_for_analytics`` only — never query
  those models here.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from app.core.enums import OutcomeEventType, VerificationTier
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummary,
    ConfidenceTierBreakdown,
    EvalScoreBucketBreakdown,
)
from app.services.generated_emails import (
    GeneratedEmailAnalyticsFields,
    list_generated_emails_for_analytics,
)
from app.services.outcomes import list_outcomes

EvalScoreBucket = Literal["<3", "3-4", "4+"]

_EVAL_BUCKET_ORDER: tuple[EvalScoreBucket, ...] = ("<3", "3-4", "4+")

_REPLY_EVENT_TYPES = frozenset(
    {OutcomeEventType.REPLIED, OutcomeEventType.INTERVIEW}
)


class _OutcomeLike(Protocol):
    """Minimal fields ``_compute_summary`` needs from an Outcome row."""

    generated_email_id: int
    event_type: OutcomeEventType


def _eval_score_bucket(eval_score: float) -> EvalScoreBucket:
    """Map ``eval_score`` into a fixed display bucket.

    Boundary inclusivity (locked — easy to get off-by-one here):
    - ``"<3"``  = ``[0, 3)``  — includes 0, excludes 3.0
    - ``"3-4"`` = ``[3, 4)``  — includes 3.0, excludes 4.0
    - ``"4+"``  = ``[4, 5]``  — includes 4.0 and 5.0
    """
    if eval_score < 3.0:
        return "<3"
    if eval_score < 4.0:
        return "3-4"
    return "4+"


def _compute_summary(
    outcomes: Sequence[_OutcomeLike],
    emails: Sequence[GeneratedEmailAnalyticsFields],
) -> AnalyticsSummary:
    """Pure reply-rate aggregation. No DB session, no current_user.

    Numerator: distinct ``generated_email_id`` with ≥1 REPLIED or INTERVIEW
    outcome (dedup by email id — multiple reply-class rows still count once).
    Denominator: distinct ``generated_email_id`` with ≥1 SENT outcome.
    Only emails in the denominator appear in totals or either breakdown;
    a generated email never marked Sent is excluded entirely.
    """
    email_by_id = {email.id: email for email in emails}

    sent_ids: set[int] = set()
    replied_ids: set[int] = set()
    for outcome in outcomes:
        email_id = outcome.generated_email_id
        if email_id not in email_by_id:
            continue
        if outcome.event_type == OutcomeEventType.SENT:
            sent_ids.add(email_id)
        elif outcome.event_type in _REPLY_EVENT_TYPES:
            replied_ids.add(email_id)

    # Reply only counts toward the rate when the email was also marked Sent.
    sent_and_replied = sent_ids & replied_ids

    total_sent = len(sent_ids)
    total_replied = len(sent_and_replied)
    overall_reply_rate: float | None = (
        total_replied / total_sent if total_sent > 0 else None
    )

    tier_sent: dict[VerificationTier, int] = defaultdict(int)
    tier_replied: dict[VerificationTier, int] = defaultdict(int)
    bucket_sent: dict[EvalScoreBucket, int] = defaultdict(int)
    bucket_replied: dict[EvalScoreBucket, int] = defaultdict(int)

    for email_id in sent_ids:
        email = email_by_id[email_id]
        did_reply = email_id in sent_and_replied
        tier = email.best_verification_tier
        bucket = _eval_score_bucket(email.eval_score)
        tier_sent[tier] += 1
        bucket_sent[bucket] += 1
        if did_reply:
            tier_replied[tier] += 1
            bucket_replied[bucket] += 1

    by_confidence_tier: list[ConfidenceTierBreakdown] = []
    for tier in VerificationTier:
        sent = tier_sent[tier]
        if sent == 0:
            continue
        replied = tier_replied[tier]
        by_confidence_tier.append(
            ConfidenceTierBreakdown(
                tier=tier,
                sent=sent,
                replied=replied,
                reply_rate=replied / sent,
            )
        )

    by_eval_score_bucket: list[EvalScoreBucketBreakdown] = []
    for bucket in _EVAL_BUCKET_ORDER:
        sent = bucket_sent[bucket]
        if sent == 0:
            continue
        replied = bucket_replied[bucket]
        by_eval_score_bucket.append(
            EvalScoreBucketBreakdown(
                bucket=bucket,
                sent=sent,
                replied=replied,
                reply_rate=replied / sent,
            )
        )

    return AnalyticsSummary(
        total_sent=total_sent,
        total_replied=total_replied,
        overall_reply_rate=overall_reply_rate,
        by_confidence_tier=by_confidence_tier,
        by_eval_score_bucket=by_eval_score_bucket,
    )


def get_reply_rate_summary(db: Session, current_user: User) -> AnalyticsSummary:
    """Load the caller's outcomes + emails, then delegate to ``_compute_summary``."""
    outcomes = list_outcomes(db, current_user)
    emails = list_generated_emails_for_analytics(db, current_user)
    return _compute_summary(outcomes, emails)
