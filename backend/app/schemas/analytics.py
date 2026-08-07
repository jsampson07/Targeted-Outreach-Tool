"""Analytics response schemas — computed on read, not persisted.

No backing table and no migration. Shapes returned by ``GET /analytics/summary``
(see ``ARCHITECTURE.md`` §10 / ``DATA_MODEL.md`` §2.10).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.core.enums import VerificationTier


class ConfidenceTierBreakdown(BaseModel):
    """Per-tier reply rate. Only included when ``sent > 0``, so ``reply_rate`` is never null."""

    tier: VerificationTier
    sent: int
    replied: int
    reply_rate: float


class EvalScoreBucketBreakdown(BaseModel):
    """Per eval-score-bucket reply rate. Only included when ``sent > 0``."""

    bucket: Literal["<3", "3-4", "4+"]
    sent: int
    replied: int
    reply_rate: float


class AnalyticsSummary(BaseModel):
    """Overall reply rate plus two separate breakdowns (not cross-tabulated)."""

    total_sent: int
    total_replied: int
    overall_reply_rate: float | None
    by_confidence_tier: list[ConfidenceTierBreakdown]
    by_eval_score_bucket: list[EvalScoreBucketBreakdown]
