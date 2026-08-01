"""HTTP tests for resume/JD extract endpoints — LLMClient mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ExperienceEntry, ResumeExtraction


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


@pytest.fixture
def company(db_session: Session) -> Company:
    row = Company(name="Extract Co", domain="extract-router.test")
    db_session.add(row)
    db_session.flush()
    return row


_RESUME_EXTRACTION = ResumeExtraction(
    skills=["Python", "SQL"],
    experience=[
        ExperienceEntry(
            company="Acme",
            title="Engineer",
            start_date="2023",
            end_date=None,
            bullet_points=["Shipped features"],
        )
    ],
    education=["BS CS"],
)

_JD_EXTRACTION = JDExtraction(
    required_skills=["Python"],
    responsibilities=["Own backend services"],
    seniority_level="junior",
)


def _mock_llm_returning(value) -> MagicMock:
    instance = MagicMock()
    instance.complete = AsyncMock(return_value=value)
    return instance


def test_extract_resume_happy_path(client: TestClient, db_session: Session):
    headers = _auth_headers(client, "resume-extract@example.com")
    me = client.get("/auth/me", headers=headers).json()
    resume = Resume(
        user_id=me["id"],
        raw_text="Jane Doe — Python engineer with SQL experience.",
        extracted_data=None,
    )
    db_session.add(resume)
    db_session.flush()

    with patch(
        "app.services.extraction.LLMClient",
        return_value=_mock_llm_returning(_RESUME_EXTRACTION),
    ):
        response = client.post(
            f"/resumes/{resume.id}/extract",
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == resume.id
    assert body["extracted_data"] == _RESUME_EXTRACTION.model_dump()


def test_extract_resume_requires_auth(client: TestClient, db_session: Session):
    response = client.post("/resumes/1/extract")
    assert response.status_code == 401


def test_extract_resume_wrong_owner_404(client: TestClient, db_session: Session):
    owner_headers = _auth_headers(client, "resume-owner-http@example.com")
    other_headers = _auth_headers(client, "resume-other-http@example.com")
    owner = client.get("/auth/me", headers=owner_headers).json()
    resume = Resume(
        user_id=owner["id"],
        raw_text="Owner resume text long enough for storage.",
        extracted_data=None,
    )
    db_session.add(resume)
    db_session.flush()

    with patch(
        "app.services.extraction.LLMClient",
        return_value=_mock_llm_returning(_RESUME_EXTRACTION),
    ):
        response = client.post(
            f"/resumes/{resume.id}/extract",
            headers=other_headers,
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "NotFoundError"


def test_extract_jd_happy_path(
    client: TestClient, db_session: Session, company: Company
):
    headers = _auth_headers(client, "jd-extract@example.com")
    me = client.get("/auth/me", headers=headers).json()
    jd = JobDescription(
        user_id=me["id"],
        company_id=company.id,
        role_title="Software Engineer",
        raw_text="Build Python services and own APIs.",
        extracted_data=None,
    )
    db_session.add(jd)
    db_session.flush()

    with patch(
        "app.services.extraction.LLMClient",
        return_value=_mock_llm_returning(_JD_EXTRACTION),
    ):
        response = client.post(
            f"/job-descriptions/{jd.id}/extract",
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == jd.id
    assert body["extracted_data"] == _JD_EXTRACTION.model_dump()


def test_extract_jd_requires_auth(client: TestClient):
    response = client.post("/job-descriptions/1/extract")
    assert response.status_code == 401


def test_extract_jd_wrong_owner_404(
    client: TestClient, db_session: Session, company: Company
):
    owner_headers = _auth_headers(client, "jd-owner-http@example.com")
    other_headers = _auth_headers(client, "jd-other-http@example.com")
    owner = client.get("/auth/me", headers=owner_headers).json()
    jd = JobDescription(
        user_id=owner["id"],
        company_id=company.id,
        role_title="Engineer",
        raw_text="Owner JD text for extraction ownership test.",
        extracted_data=None,
    )
    db_session.add(jd)
    db_session.flush()

    with patch(
        "app.services.extraction.LLMClient",
        return_value=_mock_llm_returning(_JD_EXTRACTION),
    ):
        response = client.post(
            f"/job-descriptions/{jd.id}/extract",
            headers=other_headers,
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "NotFoundError"
