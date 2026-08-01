"""Service-level tests for extraction — LLMClient mocked, real Postgres."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.models.company import Company
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ExperienceEntry, ResumeExtraction
from app.services import extraction as extraction_service


def _user(db: Session, email: str) -> User:
    user = User(email=email, password_hash=hash_password("secret-password"))
    db.add(user)
    db.flush()
    return user


def _resume(db: Session, user: User, raw_text: str = "Jane Doe Python engineer") -> Resume:
    row = Resume(user_id=user.id, raw_text=raw_text, extracted_data=None)
    db.add(row)
    db.flush()
    return row


def _company(db: Session) -> Company:
    row = Company(name="Acme", domain="acme-extract.test")
    db.add(row)
    db.flush()
    return row


def _jd(
    db: Session, user: User, company: Company, raw_text: str = "Need Python APIs"
) -> JobDescription:
    row = JobDescription(
        user_id=user.id,
        company_id=company.id,
        role_title="Engineer",
        raw_text=raw_text,
        extracted_data=None,
    )
    db.add(row)
    db.flush()
    return row


def _mock_llm(return_value) -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(return_value=return_value)
    return client


_RESUME_EXTRACTION = ResumeExtraction(
    skills=["Python"],
    experience=[
        ExperienceEntry(
            company="Acme",
            title="Engineer",
            start_date="2022",
            end_date=None,
            bullet_points=["Built APIs"],
        )
    ],
    education=["BS CS"],
)

_JD_EXTRACTION = JDExtraction(
    required_skills=["Python"],
    responsibilities=["Build APIs"],
    seniority_level="mid",
)


def test_extract_resume_happy_path(db_session: Session):
    user = _user(db_session, "extract-resume@example.com")
    resume = _resume(db_session, user)
    llm = _mock_llm(_RESUME_EXTRACTION)

    updated = asyncio.run(
        extraction_service.extract_resume(
            db_session, resume.id, user.id, llm_client=llm
        )
    )

    assert updated.extracted_data == _RESUME_EXTRACTION.model_dump()
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.args[1] is ResumeExtraction


def test_extract_resume_wrong_owner_not_found(db_session: Session):
    owner = _user(db_session, "resume-owner@example.com")
    other = _user(db_session, "resume-other@example.com")
    resume = _resume(db_session, owner)
    llm = _mock_llm(_RESUME_EXTRACTION)

    with pytest.raises(NotFoundError):
        asyncio.run(
            extraction_service.extract_resume(
                db_session, resume.id, other.id, llm_client=llm
            )
        )
    llm.complete.assert_not_awaited()


def test_extract_resume_missing_id_not_found(db_session: Session):
    user = _user(db_session, "resume-missing@example.com")
    llm = _mock_llm(_RESUME_EXTRACTION)

    with pytest.raises(NotFoundError):
        asyncio.run(
            extraction_service.extract_resume(
                db_session, 999999999, user.id, llm_client=llm
            )
        )
    llm.complete.assert_not_awaited()


def test_extract_resume_overwrites_extracted_data(db_session: Session):
    user = _user(db_session, "resume-retry@example.com")
    resume = _resume(db_session, user)
    resume.extracted_data = {
        "skills": ["Old"],
        "experience": [],
        "education": [],
    }
    db_session.flush()

    llm = _mock_llm(_RESUME_EXTRACTION)
    updated = asyncio.run(
        extraction_service.extract_resume(
            db_session, resume.id, user.id, llm_client=llm
        )
    )

    assert updated.extracted_data == _RESUME_EXTRACTION.model_dump()
    assert updated.extracted_data["skills"] == ["Python"]


def test_extract_jd_happy_path(db_session: Session):
    user = _user(db_session, "extract-jd@example.com")
    company = _company(db_session)
    jd = _jd(db_session, user, company)
    llm = _mock_llm(_JD_EXTRACTION)

    updated = asyncio.run(
        extraction_service.extract_job_description(
            db_session, jd.id, user.id, llm_client=llm
        )
    )

    assert updated.extracted_data == _JD_EXTRACTION.model_dump()
    llm.complete.assert_awaited_once()
    assert llm.complete.await_args.args[1] is JDExtraction


def test_extract_jd_wrong_owner_not_found(db_session: Session):
    owner = _user(db_session, "jd-owner@example.com")
    other = _user(db_session, "jd-other@example.com")
    company = _company(db_session)
    jd = _jd(db_session, owner, company)
    llm = _mock_llm(_JD_EXTRACTION)

    with pytest.raises(NotFoundError):
        asyncio.run(
            extraction_service.extract_job_description(
                db_session, jd.id, other.id, llm_client=llm
            )
        )
    llm.complete.assert_not_awaited()


def test_extract_jd_missing_id_not_found(db_session: Session):
    user = _user(db_session, "jd-missing@example.com")
    llm = _mock_llm(_JD_EXTRACTION)

    with pytest.raises(NotFoundError):
        asyncio.run(
            extraction_service.extract_job_description(
                db_session, 999999999, user.id, llm_client=llm
            )
        )
    llm.complete.assert_not_awaited()


def test_extract_jd_overwrites_extracted_data(db_session: Session):
    user = _user(db_session, "jd-retry@example.com")
    company = _company(db_session)
    jd = _jd(db_session, user, company)
    jd.extracted_data = {
        "required_skills": ["Cobol"],
        "responsibilities": [],
        "seniority_level": None,
    }
    db_session.flush()

    llm = _mock_llm(_JD_EXTRACTION)
    updated = asyncio.run(
        extraction_service.extract_job_description(
            db_session, jd.id, user.id, llm_client=llm
        )
    )

    assert updated.extracted_data == _JD_EXTRACTION.model_dump()
    assert updated.extracted_data["required_skills"] == ["Python"]
