"""Service-level tests for email eval / refine — LLMClient mocked, no DB."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import LLMExtractionError
from app.schemas.generated_email import (
    EmailDraft,
    EvalDimensions,
    EvalGates,
    EvalResult,
    ExperienceAlignment,
    MatchData,
    SkillMatch,
)
from app.services import eval as eval_service


_MATCH_DATA = MatchData(
    skill_matches=[
        SkillMatch(
            jd_requirement="Python",
            matched=True,
            resume_evidence="skills lists Python",
        ),
    ],
    experience_alignment=[
        ExperienceAlignment(
            jd_responsibility="Design REST APIs",
            resume_evidence="Built REST APIs",
            strength="strong",
        ),
    ],
    unmatched_jd_requirements=["Kubernetes"],
    notable_resume_strengths=["FastAPI"],
    overall_match_summary="Solid Python/API overlap.",
)

_EMAIL_DRAFT = EmailDraft(
    subject="Quick note about the Backend Engineer role",
    body="Hi Jordan,\n\nI'd love to chat about the role.\n\nBest,\nAlex",
)

_COMPANY_NAME = "Acme Corp"
_ROLE_TITLE = "Backend Engineer"

_PASSING_EVAL = EvalResult(
    gates=EvalGates(
        no_unsupported_claims=True,
        correct_contact_name_used=True,
        violation_detail=None,
    ),
    dimensions=EvalDimensions(
        role_company_specificity=4,
        relevance_alignment=4,
        tone_professionalism=5,
        conciseness=4,
        clear_cta=4,
    ),
)

_FAILING_EVAL = EvalResult(
    gates=EvalGates(
        no_unsupported_claims=False,
        correct_contact_name_used=True,
        violation_detail=(
            "Email claims Kubernetes experience, which is listed in "
            "unmatched_jd_requirements."
        ),
    ),
    dimensions=EvalDimensions(
        role_company_specificity=3,
        relevance_alignment=2,
        tone_professionalism=4,
        conciseness=3,
        clear_cta=4,
    ),
)

_REFINED_DRAFT = EmailDraft(
    subject="Quick note about the Backend Engineer role",
    body=(
        "Hi Jordan,\n\nI'd love to chat about my Python/API background "
        "for the role.\n\nBest,\nAlex"
    ),
)

_SECOND_PASS_EVAL = EvalResult(
    gates=EvalGates(
        no_unsupported_claims=True,
        correct_contact_name_used=True,
        violation_detail=None,
    ),
    dimensions=EvalDimensions(
        role_company_specificity=4,
        relevance_alignment=4,
        tone_professionalism=5,
        conciseness=4,
        clear_cta=4,
    ),
)


def _mock_llm(return_value=None, *, side_effect=None) -> MagicMock:
    client = MagicMock()
    if side_effect is not None:
        client.complete = AsyncMock(side_effect=side_effect)
    else:
        client.complete = AsyncMock(return_value=return_value)
    return client


def test_evaluate_email_happy_path():
    llm = _mock_llm(_PASSING_EVAL)

    result = asyncio.run(
        eval_service.evaluate_email(
            _EMAIL_DRAFT,
            _MATCH_DATA,
            "Jordan Lee",
            "Engineering Manager",
            _COMPANY_NAME,
            _ROLE_TITLE,
            llm_client=llm,
        )
    )

    assert result is _PASSING_EVAL
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.args[1] is EvalResult
    kwargs = llm.complete.await_args.kwargs
    if "response_schema" in kwargs:
        assert kwargs["response_schema"] is EvalResult


def test_evaluate_email_prompt_includes_company_and_role():
    llm = _mock_llm(_PASSING_EVAL)

    asyncio.run(
        eval_service.evaluate_email(
            _EMAIL_DRAFT,
            _MATCH_DATA,
            "Jordan Lee",
            "Engineering Manager",
            _COMPANY_NAME,
            _ROLE_TITLE,
            llm_client=llm,
        )
    )

    prompt = llm.complete.await_args.args[0]
    assert _COMPANY_NAME in prompt
    assert _ROLE_TITLE in prompt
    assert "trusted ground truth" in prompt
    assert "NOT part of this gate" in prompt or "not itself a claim" in prompt


def test_evaluate_email_propagates_llm_extraction_error():
    error = LLMExtractionError(detail="upstream failed")
    llm = _mock_llm(side_effect=error)

    with pytest.raises(LLMExtractionError) as exc_info:
        asyncio.run(
            eval_service.evaluate_email(
                _EMAIL_DRAFT,
                _MATCH_DATA,
                "Jordan Lee",
                "Engineering Manager",
                _COMPANY_NAME,
                _ROLE_TITLE,
                llm_client=llm,
            )
        )

    assert exc_info.value is error


def test_refine_happy_path():
    llm = _mock_llm(_REFINED_DRAFT)
    feedback = "Remove the unsupported Kubernetes claim."

    result = asyncio.run(
        eval_service.refine(_EMAIL_DRAFT, feedback, llm_client=llm)
    )

    assert result is _REFINED_DRAFT
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.args[1] is EmailDraft
    prompt = llm.complete.await_args.args[0]
    assert feedback in prompt
    assert _EMAIL_DRAFT.subject in prompt
    assert "I'd love to chat about the role." in prompt


def test_evaluate_with_retry_gate_pass_skips_refine():
    llm = _mock_llm()

    with (
        patch.object(
            eval_service,
            "evaluate_email",
            new=AsyncMock(return_value=_PASSING_EVAL),
        ) as mock_evaluate,
        patch.object(
            eval_service,
            "refine",
            new=AsyncMock(),
        ) as mock_refine,
    ):
        email, result = asyncio.run(
            eval_service.evaluate_with_retry(
                _EMAIL_DRAFT,
                _MATCH_DATA,
                "Jordan Lee",
                "Engineering Manager",
                _COMPANY_NAME,
                _ROLE_TITLE,
                llm_client=llm,
            )
        )

    assert email is _EMAIL_DRAFT
    assert result is _PASSING_EVAL
    assert mock_evaluate.await_count == 1
    mock_refine.assert_not_awaited()


def test_evaluate_with_retry_gate_fail_refines_once_and_reevaluates():
    llm = _mock_llm()
    feedback = _FAILING_EVAL.gates.violation_detail
    assert feedback is not None

    with (
        patch.object(
            eval_service,
            "evaluate_email",
            new=AsyncMock(side_effect=[_FAILING_EVAL, _SECOND_PASS_EVAL]),
        ) as mock_evaluate,
        patch.object(
            eval_service,
            "refine",
            new=AsyncMock(return_value=_REFINED_DRAFT),
        ) as mock_refine,
    ):
        email, result = asyncio.run(
            eval_service.evaluate_with_retry(
                _EMAIL_DRAFT,
                _MATCH_DATA,
                "Jordan Lee",
                "Engineering Manager",
                _COMPANY_NAME,
                _ROLE_TITLE,
                llm_client=llm,
            )
        )

    assert email is _REFINED_DRAFT
    assert result is _SECOND_PASS_EVAL
    assert mock_evaluate.await_count == 2
    mock_refine.assert_awaited_once()
    assert mock_refine.await_args.args[0] is _EMAIL_DRAFT
    assert mock_refine.await_args.args[1] == feedback
