"""Schemas for match/gap analysis (and later generated-email I/O).

``MatchData`` / ``SkillMatch`` / ``ExperienceAlignment`` are LLM structured-
output shapes with no backing table of their own — they persist later as the
``match_data`` JSONB field on ``GENERATED_EMAILS`` (DATA_MODEL.md §2.7).
``GeneratedEmailOut`` and eval schemas are deferred to a later task.
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
