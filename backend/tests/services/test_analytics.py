"""Unit tests for analytics pure aggregation — no DB fixture required."""

from types import SimpleNamespace

from app.core.enums import OutcomeEventType, VerificationTier
from app.services.analytics import _compute_summary
from app.services.generated_emails import GeneratedEmailAnalyticsFields


def _outcome(email_id: int, event_type: OutcomeEventType) -> SimpleNamespace:
    return SimpleNamespace(generated_email_id=email_id, event_type=event_type)


def _email(
    email_id: int,
    *,
    eval_score: float = 3.5,
    tier: VerificationTier = VerificationTier.VERIFIED,
) -> GeneratedEmailAnalyticsFields:
    return GeneratedEmailAnalyticsFields(
        id=email_id,
        eval_score=eval_score,
        best_verification_tier=tier,
    )


def test_no_outcomes_at_all():
    summary = _compute_summary([], [_email(1), _email(2)])
    assert summary.total_sent == 0
    assert summary.total_replied == 0
    assert summary.overall_reply_rate is None
    assert summary.by_confidence_tier == []
    assert summary.by_eval_score_bucket == []


def test_sent_with_zero_replies_gives_reply_rate_zero_not_null():
    emails = [
        _email(1, eval_score=2.0, tier=VerificationTier.VERIFIED),
        _email(2, eval_score=2.5, tier=VerificationTier.VERIFIED),
    ]
    outcomes = [
        _outcome(1, OutcomeEventType.SENT),
        _outcome(2, OutcomeEventType.SENT),
    ]
    summary = _compute_summary(outcomes, emails)

    assert summary.total_sent == 2
    assert summary.total_replied == 0
    assert summary.overall_reply_rate == 0.0
    assert len(summary.by_confidence_tier) == 1
    assert summary.by_confidence_tier[0].tier == VerificationTier.VERIFIED
    assert summary.by_confidence_tier[0].sent == 2
    assert summary.by_confidence_tier[0].replied == 0
    assert summary.by_confidence_tier[0].reply_rate == 0.0
    assert len(summary.by_eval_score_bucket) == 1
    assert summary.by_eval_score_bucket[0].bucket == "<3"
    assert summary.by_eval_score_bucket[0].reply_rate == 0.0


def test_replied_then_interview_same_email_counts_once():
    emails = [_email(10, eval_score=4.2)]
    outcomes = [
        _outcome(10, OutcomeEventType.SENT),
        _outcome(10, OutcomeEventType.REPLIED),
        _outcome(10, OutcomeEventType.INTERVIEW),
    ]
    summary = _compute_summary(outcomes, emails)

    assert summary.total_sent == 1
    assert summary.total_replied == 1
    assert summary.overall_reply_rate == 1.0


def test_interview_without_separate_replied_still_counts():
    emails = [_email(11, eval_score=4.0)]
    outcomes = [
        _outcome(11, OutcomeEventType.SENT),
        _outcome(11, OutcomeEventType.INTERVIEW),
    ]
    summary = _compute_summary(outcomes, emails)

    assert summary.total_sent == 1
    assert summary.total_replied == 1
    assert summary.overall_reply_rate == 1.0


def test_duplicate_sent_rows_still_count_once_in_denominator():
    emails = [_email(20, eval_score=3.2)]
    outcomes = [
        _outcome(20, OutcomeEventType.SENT),
        _outcome(20, OutcomeEventType.SENT),
    ]
    summary = _compute_summary(outcomes, emails)

    assert summary.total_sent == 1
    assert summary.total_replied == 0
    assert summary.overall_reply_rate == 0.0


def test_generated_email_with_no_sent_excluded_entirely():
    """REPLIED without SENT must not appear in totals or any bucket."""
    emails = [
        _email(30, eval_score=4.5, tier=VerificationTier.VERIFIED),
        _email(31, eval_score=2.0, tier=VerificationTier.PATTERN_GUESSED),
    ]
    outcomes = [
        _outcome(30, OutcomeEventType.SENT),
        _outcome(30, OutcomeEventType.REPLIED),
        # Never marked Sent — must be excluded from everything:
        _outcome(31, OutcomeEventType.REPLIED),
    ]
    summary = _compute_summary(outcomes, emails)

    assert summary.total_sent == 1
    assert summary.total_replied == 1
    assert summary.overall_reply_rate == 1.0
    assert [b.tier for b in summary.by_confidence_tier] == [
        VerificationTier.VERIFIED
    ]
    assert [b.bucket for b in summary.by_eval_score_bucket] == ["4+"]
    # pattern_guessed / <3 never appear (email 31 had no SENT)
    assert all(
        b.tier != VerificationTier.PATTERN_GUESSED
        for b in summary.by_confidence_tier
    )
    assert all(b.bucket != "<3" for b in summary.by_eval_score_bucket)


def test_eval_score_boundaries_3_and_4():
    """Exactly 3.0 → \"3-4\"; exactly 4.0 → \"4+\"."""
    emails = [
        _email(40, eval_score=3.0, tier=VerificationTier.CATCH_ALL),
        _email(41, eval_score=4.0, tier=VerificationTier.CATCH_ALL),
    ]
    outcomes = [
        _outcome(40, OutcomeEventType.SENT),
        _outcome(41, OutcomeEventType.SENT),
    ]
    summary = _compute_summary(outcomes, emails)

    buckets = {b.bucket: b for b in summary.by_eval_score_bucket}
    assert set(buckets) == {"3-4", "4+"}
    assert buckets["3-4"].sent == 1
    assert buckets["4+"].sent == 1
    assert "<3" not in buckets


def test_confidence_tier_with_zero_sent_omitted():
    emails = [
        _email(50, eval_score=3.5, tier=VerificationTier.VERIFIED),
        # Never sent — its tier must not appear even though the email exists:
        _email(51, eval_score=3.5, tier=VerificationTier.UNKNOWN),
    ]
    outcomes = [_outcome(50, OutcomeEventType.SENT)]
    summary = _compute_summary(outcomes, emails)

    tiers = [b.tier for b in summary.by_confidence_tier]
    assert tiers == [VerificationTier.VERIFIED]
    assert VerificationTier.UNKNOWN not in tiers
