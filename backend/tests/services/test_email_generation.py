"""Service-level tests for email generation — LLMClient mocked, no DB."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import LLMExtractionError
from app.schemas.generated_email import (
    EmailDraft,
    ExperienceAlignment,
    MatchData,
    SkillMatch,
)
from app.services import email_generation as email_generation_service


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
    ],
    unmatched_jd_requirements=["Kubernetes"],
    notable_resume_strengths=["FastAPI", "PostgreSQL"],
    overall_match_summary=(
        "Solid Python/API overlap; Kubernetes experience is a gap."
    ),
)

_EMAIL_DRAFT = EmailDraft(
    subject="Quick note about the Backend Engineer role at Acme",
    body=(
        "Hi Jordan,\n\nI noticed Acme's Backend Engineer opening and wanted "
        "to reach out — my recent Python/API work at Acme lines up closely "
        "with what you're hiring for. Would you be open to a brief chat?\n\n"
        "Best,\nAlex"
    ),
)


def _mock_llm(return_value=None, *, side_effect=None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.complete = AsyncMock(side_effect=side_effect)
    else:
        client.complete = AsyncMock(return_value=return_value)
    return client


def test_generate_email_happy_path():
    llm = _mock_llm(_EMAIL_DRAFT)

    result = asyncio.run(
        email_generation_service.generate_email(
            "Jordan Lee",
            "Engineering Manager",
            "Acme Corp",
            "Backend Engineer",
            _MATCH_DATA,
            llm_client=llm,
        )
    )

    assert result is _EMAIL_DRAFT
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.args[1] is EmailDraft
    kwargs = llm.complete.await_args.kwargs
    if "response_schema" in kwargs:
        assert kwargs["response_schema"] is EmailDraft


def test_generate_email_prompt_includes_match_and_context():
    llm = _mock_llm(_EMAIL_DRAFT)

    asyncio.run(
        email_generation_service.generate_email(
            "Jordan Lee",
            "Engineering Manager",
            "Acme Corp",
            "Backend Engineer",
            _MATCH_DATA,
            llm_client=llm,
        )
    )

    prompt = llm.complete.await_args.args[0]
    assert "Jordan Lee" in prompt
    assert "Engineering Manager" in prompt
    assert "Acme Corp" in prompt
    assert "Backend Engineer" in prompt
    assert "Kubernetes" in prompt  # unmatched disallow-list
    assert "Solid Python/API overlap" in prompt  # overall_match_summary
    assert "2-3" in prompt
    assert "resume dump" in prompt
    assert "Never mention, reference, imply, or acknowledge" in prompt
    assert "no acknowledgment of what's missing" in prompt
    assert "Do NOT include any sign-off" in prompt
    assert "appended programmatically" in prompt


def test_generate_email_contact_name_none_uses_fallback_greeting_instructions():
    llm = _mock_llm(
        EmailDraft(
            subject="Regarding the Backend Engineer role",
            body="Hi there,\n\nI wanted to reach out...\n",
        )
    )

    result = asyncio.run(
        email_generation_service.generate_email(
            None,
            None,
            "Acme Corp",
            "Backend Engineer",
            _MATCH_DATA,
            llm_client=llm,
        )
    )

    assert isinstance(result, EmailDraft)
    prompt = llm.complete.await_args.args[0]
    assert "null" in prompt  # contact_name serialized as null
    assert "generic" in prompt.lower()
    assert "never fabricate" in prompt.lower() or "fabricate a name" in prompt


def test_generate_email_propagates_llm_extraction_error():
    error = LLMExtractionError(detail="upstream failed")
    llm = _mock_llm(side_effect=error)

    with pytest.raises(LLMExtractionError) as exc_info:
        asyncio.run(
            email_generation_service.generate_email(
                "Jordan Lee",
                "Engineering Manager",
                "Acme Corp",
                "Backend Engineer",
                _MATCH_DATA,
                llm_client=llm,
            )
        )

    assert exc_info.value is error
