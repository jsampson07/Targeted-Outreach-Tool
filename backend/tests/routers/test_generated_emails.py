"""HTTP tests for /generated-emails — POST service mocked; GET uses real Postgres."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import VerificationTier
from app.core.exceptions import NotFoundError
from app.models.company import Company
from app.models.contact import Contact
from app.models.generated_email import GeneratedEmail
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.schemas.generated_email import (
    EvalBreakdownOut,
    EvalDimensions,
    EvalGatesOut,
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

_EVAL_BREAKDOWN_OUT = EvalBreakdownOut(
    gates=EvalGatesOut(
        no_unsupported_claims=True,
        correct_contact_name_used=True,
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
    eval_breakdown=_EVAL_BREAKDOWN_OUT,
    match_data=_MATCH_DATA,
    gate_passed=True,
    created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
)


def _seed_generated_email(
    db: Session,
    user_id: int,
    *,
    violation_detail: str | None = "Claim X is not in match_data",
) -> GeneratedEmail:
    """Insert company/contact/resume/JD/generated-email owned by ``user_id``."""
    company = Company(name="Acme Gen Get", domain=f"acme-gen-get-{user_id}.test")
    db.add(company)
    db.flush()

    contact = Contact(
        company_id=company.id,
        name="Jordan Lee",
        title="Engineering Manager",
        email=f"jordan-{user_id}@acme-gen-get.test",
        best_verification_tier=VerificationTier.VERIFIED,
        confidence_score=0.9,
        confidence_breakdown={
            "verification_tier_score": 1.0,
            "cross_provider_corroboration": False,
            "employment_currency_signal": "unknown",
            "domain_check_passed": True,
            "name_collision_detected": False,
        },
    )
    resume = Resume(
        user_id=user_id,
        raw_text="Jane Doe Python engineer with API experience.",
        extracted_data=None,
    )
    jd = JobDescription(
        user_id=user_id,
        company_id=company.id,
        role_title="Backend Engineer",
        raw_text="Need Python APIs for backend services.",
        extracted_data=None,
    )
    db.add_all([contact, resume, jd])
    db.flush()

    row = GeneratedEmail(
        contact_id=contact.id,
        resume_id=resume.id,
        job_description_id=jd.id,
        subject="Quick note about the role",
        body="Hi Jordan,\n\nWould you be open to a chat?\n\nBest,\nAlex",
        eval_score=3.0,
        eval_breakdown={
            "gates": {
                "no_unsupported_claims": False,
                "correct_contact_name_used": True,
                "violation_detail": violation_detail,
            },
            "dimensions": {
                "role_company_specificity": 5,
                "relevance_alignment": 4,
                "tone_professionalism": 3,
                "conciseness": 2,
                "clear_cta": 1,
            },
        },
        match_data=_MATCH_DATA.model_dump(),
        gate_passed=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


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
    assert "violation_detail" not in body["eval_breakdown"]["gates"]
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


def test_get_own_generated_email_happy_path(
    client: TestClient, db_session: Session
):
    headers = _auth_headers(client, "gen-owner-get@example.com")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = me.json()["id"]

    row = _seed_generated_email(db_session, user_id)
    # Confirm violation_detail is actually on the persisted JSONB row
    assert (
        row.eval_breakdown["gates"]["violation_detail"]
        == "Claim X is not in match_data"
    )

    response = client.get(f"/generated-emails/{row.id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == row.id
    assert body["contact_id"] == row.contact_id
    assert body["resume_id"] == row.resume_id
    assert body["job_description_id"] == row.job_description_id
    assert body["subject"] == row.subject
    assert body["body"] == row.body
    assert body["eval_score"] == 3.0
    assert body["gate_passed"] is False
    assert body["eval_breakdown"]["gates"]["no_unsupported_claims"] is False
    assert body["eval_breakdown"]["gates"]["correct_contact_name_used"] is True
    assert "violation_detail" not in body["eval_breakdown"]["gates"]
    assert body["match_data"]["overall_match_summary"] == "Strong overlap."
    assert "created_at" in body


def test_get_generated_email_nonexistent_is_404(client: TestClient):
    headers = _auth_headers(client, "gen-missing-get@example.com")
    response = client.get("/generated-emails/999999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["error_code"] == "NotFoundError"


def test_get_generated_email_other_users_is_404(
    client: TestClient, db_session: Session
):
    alice_headers = _auth_headers(client, "alice-gen-get@example.com")
    bob_headers = _auth_headers(client, "bob-gen-get@example.com")

    alice_me = client.get("/auth/me", headers=alice_headers)
    assert alice_me.status_code == 200
    alice_id = alice_me.json()["id"]

    row = _seed_generated_email(db_session, alice_id)

    other_users = client.get(
        f"/generated-emails/{row.id}", headers=bob_headers
    )
    missing = client.get("/generated-emails/999999999", headers=bob_headers)

    assert other_users.status_code == 404
    assert missing.status_code == 404
    assert other_users.json()["error_code"] == "NotFoundError"
    assert missing.json()["error_code"] == "NotFoundError"
    assert other_users.json()["user_message"] == missing.json()["user_message"]
