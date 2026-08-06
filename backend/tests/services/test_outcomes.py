"""Service-level tests for outcomes — append-only create/list, real Postgres."""

import pytest
from sqlalchemy.orm import Session

from app.core.enums import OutcomeEventType, VerificationTier
from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.models.company import Company
from app.models.contact import Contact
from app.models.generated_email import GeneratedEmail
from app.models.job_description import JobDescription
from app.models.outcome import Outcome
from app.models.resume import Resume
from app.models.user import User
from app.schemas.outcome import OutcomeCreate
from app.services import outcomes as outcomes_service


def _user(db: Session, email: str) -> User:
    user = User(email=email, password_hash=hash_password("secret-password"))
    db.add(user)
    db.flush()
    return user


def _company(db: Session, domain: str = "acme-outcome.test") -> Company:
    row = Company(name="Acme Corp", domain=domain)
    db.add(row)
    db.flush()
    return row


def _contact(db: Session, company: Company) -> Contact:
    row = Contact(
        company_id=company.id,
        name="Jordan Lee",
        title="Engineering Manager",
        email="jordan@acme-outcome.test",
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


def _resume(db: Session, user: User) -> Resume:
    row = Resume(
        user_id=user.id,
        raw_text="Jane Doe Python engineer with API experience.",
        extracted_data=None,
    )
    db.add(row)
    db.flush()
    return row


def _jd(db: Session, user: User, company: Company) -> JobDescription:
    row = JobDescription(
        user_id=user.id,
        company_id=company.id,
        role_title="Backend Engineer",
        raw_text="Need Python APIs for backend services.",
        extracted_data=None,
    )
    db.add(row)
    db.flush()
    return row


def _generated_email(
    db: Session, user: User, *, domain: str = "acme-outcome.test"
) -> GeneratedEmail:
    """Insert a GENERATED_EMAILS row owned by ``user`` via resume ownership."""
    company = _company(db, domain=domain)
    contact = _contact(db, company)
    resume = _resume(db, user)
    jd = _jd(db, user, company)
    row = GeneratedEmail(
        contact_id=contact.id,
        resume_id=resume.id,
        job_description_id=jd.id,
        subject="Quick note",
        body="Hi Jordan,\n\nWould you be open to a brief chat?\n\nBest regards,",
        eval_score=3.0,
        eval_breakdown={
            "gates": {
                "no_unsupported_claims": True,
                "correct_contact_name_used": True,
                "no_unprompted_gap_admission": True,
            },
            "dimensions": {
                "role_company_specificity": 3,
                "relevance_alignment": 3,
                "tone_professionalism": 3,
                "conciseness": 3,
                "clear_cta": 3,
            },
        },
        match_data={
            "skill_matches": [],
            "experience_alignment": [],
            "unmatched_jd_requirements": [],
            "notable_resume_strengths": [],
            "overall_match_summary": "ok",
        },
        gate_passed=True,
    )
    db.add(row)
    db.flush()
    return row


def test_create_outcome_wrong_owner_raises_not_found(db_session: Session):
    owner = _user(db_session, "outcome-owner@example.com")
    other = _user(db_session, "outcome-other@example.com")
    email = _generated_email(db_session, owner, domain="outcome-wrong-owner.test")

    with pytest.raises(NotFoundError):
        outcomes_service.create_outcome(
            db_session,
            other,
            OutcomeCreate(
                generated_email_id=email.id,
                event_type=OutcomeEventType.SENT,
            ),
        )

    assert db_session.query(Outcome).count() == 0


def test_create_multiple_outcomes_same_email_succeeds(db_session: Session):
    user = _user(db_session, "outcome-append@example.com")
    email = _generated_email(db_session, user, domain="outcome-append.test")

    first = outcomes_service.create_outcome(
        db_session,
        user,
        OutcomeCreate(
            generated_email_id=email.id,
            event_type=OutcomeEventType.SENT,
        ),
    )
    second = outcomes_service.create_outcome(
        db_session,
        user,
        OutcomeCreate(
            generated_email_id=email.id,
            event_type=OutcomeEventType.REPLIED,
        ),
    )

    assert first.id != second.id
    assert first.user_id == user.id
    assert second.user_id == user.id
    assert first.generated_email_id == email.id
    assert second.generated_email_id == email.id
    assert first.event_type == OutcomeEventType.SENT
    assert second.event_type == OutcomeEventType.REPLIED
    assert db_session.query(Outcome).count() == 2


def test_list_outcomes_scoped_and_filterable(db_session: Session):
    alice = _user(db_session, "outcome-alice@example.com")
    bob = _user(db_session, "outcome-bob@example.com")
    alice_email_a = _generated_email(
        db_session, alice, domain="outcome-alice-a.test"
    )
    alice_email_b = _generated_email(
        db_session, alice, domain="outcome-alice-b.test"
    )
    bob_email = _generated_email(db_session, bob, domain="outcome-bob.test")

    outcomes_service.create_outcome(
        db_session,
        alice,
        OutcomeCreate(
            generated_email_id=alice_email_a.id,
            event_type=OutcomeEventType.SENT,
        ),
    )
    outcomes_service.create_outcome(
        db_session,
        alice,
        OutcomeCreate(
            generated_email_id=alice_email_b.id,
            event_type=OutcomeEventType.NO_RESPONSE,
        ),
    )
    outcomes_service.create_outcome(
        db_session,
        bob,
        OutcomeCreate(
            generated_email_id=bob_email.id,
            event_type=OutcomeEventType.INTERVIEW,
        ),
    )

    alice_all = outcomes_service.list_outcomes(db_session, alice)
    assert len(alice_all) == 2
    assert {row.generated_email_id for row in alice_all} == {
        alice_email_a.id,
        alice_email_b.id,
    }

    alice_filtered = outcomes_service.list_outcomes(
        db_session, alice, generated_email_id=alice_email_a.id
    )
    assert len(alice_filtered) == 1
    assert alice_filtered[0].generated_email_id == alice_email_a.id
    assert alice_filtered[0].event_type == OutcomeEventType.SENT

    bob_all = outcomes_service.list_outcomes(db_session, bob)
    assert len(bob_all) == 1
    assert bob_all[0].generated_email_id == bob_email.id
