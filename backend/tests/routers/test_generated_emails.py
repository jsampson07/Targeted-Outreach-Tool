"""HTTP tests for POST /generated-emails — service layer mocked."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError
from app.schemas.generated_email import (
    EvalBreakdown,
    EvalDimensions,
    EvalGates,
    ExperienceAlignment,
    GeneratedEmailOut,
    MatchData,
    SkillMatch,
)


def _signup(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = "secret-password",
):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )


def _auth_headers(
    client: TestClient, email: str, password: str = "secret-password"
) -> dict:
    signup = _signup(client, email=email, password=password)
    assert signup.status_code == 201
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


_MATCH_DATA = MatchData(
    skill_matches=[
        SkillMatch(
            jd_requirement="Python",
            matched=True,
            resume_evidence="skills lists Python",
        )
    ],
    experience_alignment=[
        ExperienceAlignment(
            jd_responsibility="Build APIs",
            resume_evidence="Built APIs",
            strength="strong",
        )
    ],
    unmatched_jd_requirements=[],
    notable_resume_strengths=["FastAPI"],
    overall_match_summary="Strong overlap.",
)

_EVAL_BREAKDOWN = EvalBreakdown(
    gates=EvalGates(
        no_unsupported_claims=True,
        correct_contact_name_used=True,
        violation_detail=None,
    ),
    dimensions=EvalDimensions(
        role_company_specificity=5,
        relevance_alignment=4,
        tone_professionalism=3,
        conciseness=2,
        clear_cta=1,
    ),
)

_GENERATED_OUT = GeneratedEmailOut(
    id=42,
    contact_id=1,
    resume_id=2,
    job_description_id=3,
    subject="Quick note about the role",
    body="Hi Jordan,\n\nWould you be open to a chat?\n\nBest,\nAlex",
    eval_score=3.0,
    eval_breakdown=_EVAL_BREAKDOWN,
    match_data=_MATCH_DATA,
    gate_passed=True,
    created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
)


def test_generate_email_requires_auth(client: TestClient):
    response = client.post(
        "/generated-emails",
        json={
            "contact_id": 1,
            "resume_id": 1,
            "job_description_id": 1,
        },
    )
    assert response.status_code == 401


def test_generate_email_happy_path(client: TestClient):
    headers = _auth_headers(client, "gen-router-happy@example.com")

    with patch(
        "app.routers.generated_emails.generate_and_persist_email",
        new_callable=AsyncMock,
        return_value=_GENERATED_OUT,
    ) as mock_svc:
        response = client.post(
            "/generated-emails",
            headers=headers,
            json={
                "contact_id": 1,
                "resume_id": 2,
                "job_description_id": 3,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 42
    assert body["contact_id"] == 1
    assert body["resume_id"] == 2
    assert body["job_description_id"] == 3
    assert body["subject"] == _GENERATED_OUT.subject
    assert body["body"] == _GENERATED_OUT.body
    assert body["eval_score"] == 3.0
    assert body["gate_passed"] is True
    assert body["eval_breakdown"]["gates"]["no_unsupported_claims"] is True
    assert body["match_data"]["overall_match_summary"] == "Strong overlap."
    assert "created_at" in body
    mock_svc.assert_awaited_once()
    call_kwargs = mock_svc.await_args
    assert call_kwargs.args[2] == 1  # contact_id
    assert call_kwargs.args[3] == 2  # resume_id
    assert call_kwargs.args[4] == 3  # job_description_id


def test_generate_email_not_found_ids(client: TestClient):
    headers = _auth_headers(client, "gen-router-404@example.com")

    with patch(
        "app.routers.generated_emails.generate_and_persist_email",
        new_callable=AsyncMock,
        side_effect=NotFoundError(detail="Resume id=999 not found for user"),
    ):
        response = client.post(
            "/generated-emails",
            headers=headers,
            json={
                "contact_id": 1,
                "resume_id": 999,
                "job_description_id": 1,
            },
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "NotFoundError"
