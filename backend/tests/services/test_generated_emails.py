"""Service-level tests for generate_and_persist_email — LLM mocked, real Postgres."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.core.enums import VerificationTier
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.company import Company
from app.models.contact import Contact
from app.models.generated_email import GeneratedEmail
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.schemas.generated_email import (
    EmailDraft,
    EvalDimensions,
    EvalGates,
    EvalResult,
    ExperienceAlignment,
    MatchData,
    SkillMatch,
)
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ExperienceEntry, ResumeExtraction
from app.services import generated_emails as generated_emails_service


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
            resume_evidence="Built APIs at Acme",
            strength="strong",
        )
    ],
    unmatched_jd_requirements=[],
    notable_resume_strengths=["FastAPI"],
    overall_match_summary="Strong Python/API overlap.",
)

_EMAIL_DRAFT = EmailDraft(
    subject="Quick note about the Backend Engineer role",
    body="Hi Jordan,\n\nWould you be open to a brief chat?\n\nBest,\nAlex",
)

# Dimensions 5+4+3+2+1 = 15 → mean 3.0
_EVAL_RESULT = EvalResult(
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


def _user(db: Session, email: str) -> User:
    user = User(email=email, password_hash=hash_password("secret-password"))
    db.add(user)
    db.flush()
    return user


def _company(db: Session, domain: str = "acme-gen.test") -> Company:
    row = Company(name="Acme Corp", domain=domain)
    db.add(row)
    db.flush()
    return row


def _contact(db: Session, company: Company) -> Contact:
    row = Contact(
        company_id=company.id,
        name="Jordan Lee",
        title="Engineering Manager",
        email="jordan@acme-gen.test",
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
    db.add(row)
    db.flush()
    return row


def _resume(
    db: Session,
    user: User,
    *,
    extracted: bool = True,
) -> Resume:
    row = Resume(
        user_id=user.id,
        raw_text="Jane Doe Python engineer with API experience.",
        extracted_data=_RESUME_EXTRACTION.model_dump() if extracted else None,
    )
    db.add(row)
    db.flush()
    return row


def _jd(
    db: Session,
    user: User,
    company: Company,
    *,
    extracted: bool = True,
) -> JobDescription:
    row = JobDescription(
        user_id=user.id,
        company_id=company.id,
        role_title="Backend Engineer",
        raw_text="Need Python APIs for backend services.",
        extracted_data=_JD_EXTRACTION.model_dump() if extracted else None,
    )
    db.add(row)
    db.flush()
    return row


def _patch_llm_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        generated_emails_service,
        "generate_match_data",
        AsyncMock(return_value=_MATCH_DATA),
    )
    monkeypatch.setattr(
        generated_emails_service,
        "generate_email",
        AsyncMock(return_value=_EMAIL_DRAFT),
    )
    monkeypatch.setattr(
        generated_emails_service,
        "evaluate_with_retry",
        AsyncMock(return_value=(_EMAIL_DRAFT, _EVAL_RESULT)),
    )


def test_generate_and_persist_happy_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-happy@example.com")
    company = _company(db_session)
    contact = _contact(db_session, company)
    resume = _resume(db_session, user)
    jd = _jd(db_session, user, company)

    row = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )

    assert isinstance(row, GeneratedEmail)
    assert row.id is not None
    assert row.contact_id == contact.id
    assert row.resume_id == resume.id
    assert row.job_description_id == jd.id
    assert row.subject == _EMAIL_DRAFT.subject
    assert row.body == _EMAIL_DRAFT.body
    assert row.eval_score == pytest.approx(3.0)
    assert row.gate_passed is True
    assert row.match_data == _MATCH_DATA.model_dump()
    assert row.eval_breakdown == _EVAL_RESULT.model_dump()

    persisted = (
        db_session.query(GeneratedEmail)
        .filter(GeneratedEmail.id == row.id)
        .one()
    )
    assert persisted.eval_score == pytest.approx(3.0)


def test_wrong_owner_resume_not_found(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    owner = _user(db_session, "gen-resume-owner@example.com")
    other = _user(db_session, "gen-resume-other@example.com")
    company = _company(db_session, domain="acme-resume-owner.test")
    contact = _contact(db_session, company)
    resume = _resume(db_session, owner)
    jd = _jd(db_session, other, company)

    with pytest.raises(NotFoundError):
        asyncio.run(
            generated_emails_service.generate_and_persist_email(
                db_session, other, contact.id, resume.id, jd.id
            )
        )
    assert db_session.query(GeneratedEmail).count() == 0


def test_wrong_owner_jd_not_found(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    owner = _user(db_session, "gen-jd-owner@example.com")
    other = _user(db_session, "gen-jd-other@example.com")
    company = _company(db_session, domain="acme-jd-owner.test")
    contact = _contact(db_session, company)
    resume = _resume(db_session, other)
    jd = _jd(db_session, owner, company)

    with pytest.raises(NotFoundError):
        asyncio.run(
            generated_emails_service.generate_and_persist_email(
                db_session, other, contact.id, resume.id, jd.id
            )
        )
    assert db_session.query(GeneratedEmail).count() == 0


def test_missing_contact_not_found(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-missing-contact@example.com")
    company = _company(db_session, domain="acme-missing-contact.test")
    resume = _resume(db_session, user)
    jd = _jd(db_session, user, company)

    with pytest.raises(NotFoundError):
        asyncio.run(
            generated_emails_service.generate_and_persist_email(
                db_session, user, 999999999, resume.id, jd.id
            )
        )
    assert db_session.query(GeneratedEmail).count() == 0


def test_resume_missing_extracted_data_validation_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-no-resume-extract@example.com")
    company = _company(db_session, domain="acme-no-resume-extract.test")
    contact = _contact(db_session, company)
    resume = _resume(db_session, user, extracted=False)
    jd = _jd(db_session, user, company)

    with pytest.raises(ValidationError, match="Resume"):
        asyncio.run(
            generated_emails_service.generate_and_persist_email(
                db_session, user, contact.id, resume.id, jd.id
            )
        )
    assert db_session.query(GeneratedEmail).count() == 0


def test_jd_missing_extracted_data_validation_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-no-jd-extract@example.com")
    company = _company(db_session, domain="acme-no-jd-extract.test")
    contact = _contact(db_session, company)
    resume = _resume(db_session, user)
    jd = _jd(db_session, user, company, extracted=False)

    with pytest.raises(ValidationError, match="JobDescription"):
        asyncio.run(
            generated_emails_service.generate_and_persist_email(
                db_session, user, contact.id, resume.id, jd.id
            )
        )
    assert db_session.query(GeneratedEmail).count() == 0


def test_company_mismatch_validation_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-company-mismatch@example.com")
    company_a = _company(db_session, domain="acme-a.test")
    company_b = _company(db_session, domain="acme-b.test")
    contact = _contact(db_session, company_a)
    resume = _resume(db_session, user)
    jd = _jd(db_session, user, company_b)

    with pytest.raises(ValidationError, match="does not match"):
        asyncio.run(
            generated_emails_service.generate_and_persist_email(
                db_session, user, contact.id, resume.id, jd.id
            )
        )
    assert db_session.query(GeneratedEmail).count() == 0


def test_regeneration_inserts_second_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-insert-twice@example.com")
    company = _company(db_session, domain="acme-insert-twice.test")
    contact = _contact(db_session, company)
    resume = _resume(db_session, user)
    jd = _jd(db_session, user, company)

    first = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )
    second = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )

    assert first.id != second.id
    rows = (
        db_session.query(GeneratedEmail)
        .filter(
            GeneratedEmail.contact_id == contact.id,
            GeneratedEmail.resume_id == resume.id,
            GeneratedEmail.job_description_id == jd.id,
        )
        .all()
    )
    assert len(rows) == 2
    assert {rows[0].id, rows[1].id} == {first.id, second.id}
