"""Schemas for match/gap analysis, email drafts, eval I/O, and generated-email API.

``MatchData`` / ``SkillMatch`` / ``ExperienceAlignment`` are LLM structured-
output shapes with no backing table of their own — they persist as the
``match_data`` JSONB field on ``GENERATED_EMAILS`` (DATA_MODEL.md §2.7).
``EmailDraft`` is the ephemeral generation/refine output shape (subject/body
only) — not persisted on its own. ``EvalResult`` / ``EvalBreakdown`` are the
LLM-judge shapes (including ``violation_detail`` for refine). The persisted
breakdown is returned via ``GeneratedEmailOut`` using ``EvalBreakdownOut``,
which strips ``violation_detail`` at the API boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


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
    """Internal judge/refine shape — includes violation_detail for refine()."""

    no_unsupported_claims: bool
    correct_contact_name_used: bool
    # Default True so pre-existing eval_breakdown JSONB rows (2-gate era)
    # still deserialize; those rows keep their original gate_passed value.
    no_unprompted_gap_admission: bool = True
    violation_detail: str | None = None


class EvalGatesOut(BaseModel):
    """Client-facing gates — omits violation_detail (internal refine feedback)."""

    no_unsupported_claims: bool
    correct_contact_name_used: bool
    no_unprompted_gap_admission: bool = True


class EvalDimensions(BaseModel):
    role_company_specificity: int  # 1-5
    relevance_alignment: int
    tone_professionalism: int
    conciseness: int
    clear_cta: int


class EvalBreakdown(BaseModel):
    gates: EvalGates
    dimensions: EvalDimensions


class EvalBreakdownOut(BaseModel):
    """Client-facing breakdown — gates omit violation_detail."""

    gates: EvalGatesOut
    dimensions: EvalDimensions


class EvalResult(EvalBreakdown):
    """Raw shape returned by the LLM-judge call — before refine() / persist."""

    pass


class GenerateEmailRequest(BaseModel):
    contact_id: int
    resume_id: int
    job_description_id: int


class GeneratedEmailOut(BaseModel):
    id: int
    contact_id: int
    resume_id: int
    job_description_id: int
    subject: str
    body: str
    eval_score: float
    eval_breakdown: EvalBreakdownOut
    match_data: MatchData
    gate_passed: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GeneratedEmailListOut(BaseModel):
    """Display-focused list shape for a past-email picker — not a full row.

    Omits body, eval_breakdown, and match_data (not needed to identify which
    email to act on). Contact/company fields are joined at read time; this
    endpoint deliberately does not include outcome status.
    """

    id: int
    subject: str
    contact_name: str | None
    contact_title: str | None
    company_name: str
    eval_score: float
    gate_passed: bool
    created_at: datetime
