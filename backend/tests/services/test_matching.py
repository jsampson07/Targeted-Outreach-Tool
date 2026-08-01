"""Service-level tests for match/gap analysis — LLMClient mocked, no DB."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import LLMExtractionError
from app.schemas.generated_email import (
    ExperienceAlignment,
    MatchData,
    SkillMatch,
)
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ExperienceEntry, ResumeExtraction
from app.services import matching as matching_service


_RESUME_EXTRACTION = ResumeExtraction(
    skills=["Python", "FastAPI", "PostgreSQL"],
    experience=[
        ExperienceEntry(
            company="Acme",
            title="Backend Engineer",
            start_date="2022",
            end_date=None,
            bullet_points=["Built REST APIs in Python"],
        )
    ],
    education=["BS Computer Science"],
)

_JD_EXTRACTION = JDExtraction(
    required_skills=["Python", "Kubernetes"],
    responsibilities=["Design REST APIs", "Own on-call rotations"],
    seniority_level="mid",
)

_MATCH_DATA = MatchData(
    skill_matches=[
        SkillMatch(
            jd_requirement="Python",
            matched=True,
            resume_evidence="skills lists Python; API work at Acme",
        ),
        SkillMatch(
            jd_requirement="Kubernetes",
            matched=False,
            resume_evidence=None,
        ),
    ],
    experience_alignment=[
        ExperienceAlignment(
            jd_responsibility="Design REST APIs",
            resume_evidence="Built REST APIs in Python at Acme",
            strength="strong",
        ),
        ExperienceAlignment(
            jd_responsibility="Own on-call rotations",
            resume_evidence=None,
            strength="none",
        ),
    ],
    unmatched_jd_requirements=["Kubernetes"],
    notable_resume_strengths=["FastAPI", "PostgreSQL"],
    overall_match_summary=(
        "Solid Python/API overlap; Kubernetes and on-call experience are gaps."
    ),
)


def _mock_llm(return_value=None, *, side_effect=None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.complete = AsyncMock(side_effect=side_effect)
    else:
        client.complete = AsyncMock(return_value=return_value)
    return client


def test_generate_match_data_happy_path():
    llm = _mock_llm(_MATCH_DATA)

    result = asyncio.run(
        matching_service.generate_match_data(
            _RESUME_EXTRACTION,
            _JD_EXTRACTION,
            llm_client=llm,
        )
    )

    assert result is _MATCH_DATA
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.args[1] is MatchData
    # Keyword form is also acceptable if the service uses it.
    kwargs = llm.complete.await_args.kwargs
    if "response_schema" in kwargs:
        assert kwargs["response_schema"] is MatchData


def test_generate_match_data_prompt_includes_both_inputs():
    llm = _mock_llm(_MATCH_DATA)

    asyncio.run(
        matching_service.generate_match_data(
            _RESUME_EXTRACTION,
            _JD_EXTRACTION,
            llm_client=llm,
        )
    )

    prompt = llm.complete.await_args.args[0]
    assert "Kubernetes" in prompt  # JD-specific skill
    assert "FastAPI" in prompt  # resume-specific skill
    assert "Design REST APIs" in prompt  # JD responsibility
    assert "Built REST APIs in Python" in prompt  # resume evidence


def test_generate_match_data_propagates_llm_extraction_error():
    error = LLMExtractionError(detail="upstream failed")
    llm = _mock_llm(side_effect=error)

    with pytest.raises(LLMExtractionError) as exc_info:
        asyncio.run(
            matching_service.generate_match_data(
                _RESUME_EXTRACTION,
                _JD_EXTRACTION,
                llm_client=llm,
            )
        )

    assert exc_info.value is error
