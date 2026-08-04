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
    body="Hi Jordan,\n\nWould you be open to a brief chat?",
)

_UNSIGNED_CLOSING = "\n\nBest regards,"

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
    assert row.body == f"{_EMAIL_DRAFT.body}{_UNSIGNED_CLOSING}"
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


def test_strip_trailing_closing_no_closing_unchanged():
    body = "Hi Jordan,\n\nWould you be open to a brief chat?"
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == body
    )


def test_strip_trailing_closing_standalone_best():
    body = "Hi Jordan,\n\nWould you be open to a brief chat?\n\nBest,"
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == "Hi Jordan,\n\nWould you be open to a brief chat?"
    )


def test_strip_trailing_closing_phrase_plus_candidate_name():
    body = (
        "Hi Jordan,\n\nWould you be open to a brief chat?\n\n"
        "Best regards,\nJane Doe"
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == "Hi Jordan,\n\nWould you be open to a brief chat?"
    )


def test_strip_trailing_closing_mid_sentence_thanks_not_stripped():
    body = (
        "Hi Jordan,\n\nThanks for your time and consideration."
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == body
    )


def test_strip_trailing_closing_mid_sentence_regards_not_stripped():
    body = (
        "Hi Jordan,\n\nI wanted to share my regards for the team's work."
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == body
    )


@pytest.mark.parametrize(
    "closing_line",
    [
        "Best regards",
        "BEST,",
        "Sincerely.",
        "warm regards,",
        "Kind Regards.",
        "thanks",
        "Thank you,",
    ],
)
def test_strip_trailing_closing_case_and_punctuation_variants(closing_line: str):
    body = f"Hi Jordan,\n\nWould you be open to a brief chat?\n\n{closing_line}"
    assert (
        generated_emails_service._strip_trailing_closing(body, None)
        == "Hi Jordan,\n\nWould you be open to a brief chat?"
    )


def test_strip_trailing_closing_phrase_then_trailing_sentence():
    """Valediction followed by non-name prose — both stripped (dogfood round 2)."""
    body = (
        "Hi Jordan,\n\nWould you have time for a brief call next week?\n\n"
        "Thanks,\nLooking forward to hearing from you."
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == "Hi Jordan,\n\nWould you have time for a brief call next week?"
    )


def test_strip_trailing_closing_stacked_closings_plus_name():
    body = (
        "Hi Jordan,\n\nWould you be open to a brief chat?\n\n"
        "Thanks,\nBest,\nJane Doe"
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == "Hi Jordan,\n\nWould you be open to a brief chat?"
    )


def test_strip_trailing_closing_bare_candidate_name():
    body = (
        "Hi Jordan,\n\nWould you be open to a brief chat?\n\nJane Doe"
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == "Hi Jordan,\n\nWould you be open to a brief chat?"
    )


def test_strip_trailing_closing_anchor_not_bottom_most_sweeps_to_end():
    """Closing phrase mid-window with a short trailing sentence below it."""
    body = (
        "Hi Jordan,\n\nExcited about the Backend Engineer role.\n\n"
        "Best regards,\nHope to connect soon."
    )
    assert (
        generated_emails_service._strip_trailing_closing(body, "Jane Doe")
        == "Hi Jordan,\n\nExcited about the Backend Engineer role."
    )


def test_signature_appends_candidate_name(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-sig-named@example.com")
    company = _company(db_session, domain="acme-sig-named.test")
    contact = _contact(db_session, company)
    extraction = _RESUME_EXTRACTION.model_copy(
        update={"candidate_name": "Jane Doe"}
    )
    resume = Resume(
        user_id=user.id,
        raw_text="Jane Doe Python engineer with API experience.",
        extracted_data=extraction.model_dump(),
    )
    db_session.add(resume)
    db_session.flush()
    jd = _jd(db_session, user, company)

    row = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )

    assert row.body == f"{_EMAIL_DRAFT.body}\n\nBest regards,\nJane Doe"
    assert row.body.count("Best regards,") == 1


def test_signature_omits_name_when_candidate_name_none(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    _patch_llm_pipeline(monkeypatch)
    user = _user(db_session, "gen-sig-none@example.com")
    company = _company(db_session, domain="acme-sig-none.test")
    contact = _contact(db_session, company)
    resume = _resume(db_session, user)
    jd = _jd(db_session, user, company)

    row = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )

    assert row.body == f"{_EMAIL_DRAFT.body}{_UNSIGNED_CLOSING}"
    assert not row.body.endswith("\nNone")
    assert "Jane Doe" not in row.body
    assert row.body.count("Best regards,") == 1


def test_signature_strips_model_closing_before_append(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Model-authored 'Best,' is stripped so only the programmatic signature remains."""
    draft_with_closing = EmailDraft(
        subject=_EMAIL_DRAFT.subject,
        body=f"{_EMAIL_DRAFT.body}\n\nBest,",
    )
    monkeypatch.setattr(
        generated_emails_service,
        "generate_match_data",
        AsyncMock(return_value=_MATCH_DATA),
    )
    monkeypatch.setattr(
        generated_emails_service,
        "generate_email",
        AsyncMock(return_value=draft_with_closing),
    )
    monkeypatch.setattr(
        generated_emails_service,
        "evaluate_with_retry",
        AsyncMock(return_value=(draft_with_closing, _EVAL_RESULT)),
    )

    user = _user(db_session, "gen-sig-strip@example.com")
    company = _company(db_session, domain="acme-sig-strip.test")
    contact = _contact(db_session, company)
    extraction = _RESUME_EXTRACTION.model_copy(
        update={"candidate_name": "Jane Doe"}
    )
    resume = Resume(
        user_id=user.id,
        raw_text="Jane Doe Python engineer with API experience.",
        extracted_data=extraction.model_dump(),
    )
    db_session.add(resume)
    db_session.flush()
    jd = _jd(db_session, user, company)

    row = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )

    assert row.body == f"{_EMAIL_DRAFT.body}\n\nBest regards,\nJane Doe"
    assert row.body.count("Best regards,") == 1
    assert "\nBest,\n" not in row.body
    assert not row.body.startswith("Best,")


def test_signature_appended_once_after_refine_pass(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Strip + signature run once on the final draft — not on intermediate refine attempts."""
    refined = EmailDraft(
        subject="Refined subject",
        body=(
            "Hi Jordan,\n\nRevised body after gate feedback.\n\n"
            "Best,\nAlex Rivera"
        ),
    )
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
        AsyncMock(return_value=(refined, _EVAL_RESULT)),
    )

    user = _user(db_session, "gen-sig-refine@example.com")
    company = _company(db_session, domain="acme-sig-refine.test")
    contact = _contact(db_session, company)
    extraction = _RESUME_EXTRACTION.model_copy(
        update={"candidate_name": "Alex Rivera"}
    )
    resume = Resume(
        user_id=user.id,
        raw_text="Alex Rivera Python engineer.",
        extracted_data=extraction.model_dump(),
    )
    db_session.add(resume)
    db_session.flush()
    jd = _jd(db_session, user, company)

    row = asyncio.run(
        generated_emails_service.generate_and_persist_email(
            db_session, user, contact.id, resume.id, jd.id
        )
    )

    assert row.body == (
        "Hi Jordan,\n\nRevised body after gate feedback."
        "\n\nBest regards,\nAlex Rivera"
    )
    assert row.body.count("Best regards,") == 1
    assert row.body.count("Alex Rivera") == 1
    assert row.body.count("Best,") == 0
