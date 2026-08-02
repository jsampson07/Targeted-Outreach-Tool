"""Schemas for match/gap analysis, email drafts, and eval I/O.

``MatchData`` / ``SkillMatch`` / ``ExperienceAlignment`` are LLM structured-
output shapes with no backing table of their own — they persist later as the
``match_data`` JSONB field on ``GENERATED_EMAILS`` (DATA_MODEL.md §2.7).
``EmailDraft`` is the ephemeral generation/refine output shape (subject/body
only) — not persisted on its own. ``EvalResult`` / ``EvalBreakdown`` are the
LLM-judge shapes; persistence of ``eval_breakdown`` on ``GENERATED_EMAILS``
(and ``GeneratedEmailOut``) is deferred to the persistence/router task.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SkillMatch(BaseModel):
    jd_requirement: str
    matched: bool
    resume_evidence: str | None


class ExperienceAlignment(BaseModel):
    jd_responsibility: str
    resume_evidence: str | None
    strength: Literal["strong", "partial", "none"]


class MatchData(BaseModel):
    skill_matches: list[SkillMatch]
    experience_alignment: list[ExperienceAlignment]
    unmatched_jd_requirements: list[str]
    notable_resume_strengths: list[str]
    overall_match_summary: str


class EmailDraft(BaseModel):
    subject: str
    body: str


class EvalGates(BaseModel):
    no_unsupported_claims: bool
    correct_contact_name_used: bool
    violation_detail: str | None = None


class EvalDimensions(BaseModel):
    role_company_specificity: int  # 1-5
    relevance_alignment: int
    tone_professionalism: int
    conciseness: int
    clear_cta: int


class EvalBreakdown(BaseModel):
    gates: EvalGates
    dimensions: EvalDimensions


class EvalResult(EvalBreakdown):
    """Raw shape returned by the LLM-judge call — before refine() / persist."""

    pass
