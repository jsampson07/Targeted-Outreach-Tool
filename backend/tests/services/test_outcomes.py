"""Service-level tests for outcomes — append-only create/list, real Postgres."""

import pytest
from sqlalchemy.orm import Session

from app.core.enums import OutcomeEventType, VerificationTier
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.company import Company
from app.models.contact import Contact
from app.models.generated_email import GeneratedEmail
from app.models.job_description import JobDescription
from app.models.outcome import Outcome
from app.models.resume import Resume
from app.models.user import User
from app.schemas.outcome import OutcomeCreate, OutcomeOut
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


def _create(
    db: Session,
    user: User,
    email_id: int,
    event_type: OutcomeEventType,
) -> Outcome:
    return outcomes_service.create_outcome(
        db,
        user,
        OutcomeCreate(generated_email_id=email_id, event_type=event_type),
    )


def test_create_outcome_wrong_owner_raises_not_found(db_session: Session):
    owner = _user(db_session, "outcome-owner@example.com")
    other = _user(db_session, "outcome-other@example.com")
    email = _generated_email(db_session, owner, domain="outcome-wrong-owner.test")

    with pytest.raises(NotFoundError):
        _create(db_session, other, email.id, OutcomeEventType.SENT)

    assert (
        db_session.query(Outcome)
        .filter(Outcome.generated_email_id == email.id)
        .count()
        == 0
    )


def test_create_multiple_outcomes_same_email_succeeds(db_session: Session):
    """SENT then REPLIED is the allowed funnel — not a second SENT."""
    user = _user(db_session, "outcome-append@example.com")
    email = _generated_email(db_session, user, domain="outcome-append.test")

    first = _create(db_session, user, email.id, OutcomeEventType.SENT)
    second = _create(db_session, user, email.id, OutcomeEventType.REPLIED)

    assert first.id != second.id
    assert first.user_id == user.id
    assert second.user_id == user.id
    assert first.generated_email_id == email.id
    assert second.generated_email_id == email.id
    assert first.event_type == OutcomeEventType.SENT
    assert second.event_type == OutcomeEventType.REPLIED
    assert (
        db_session.query(Outcome)
        .filter(Outcome.generated_email_id == email.id)
        .count()
        == 2
    )


def test_create_duplicate_sent_raises_validation_error(db_session: Session):
    user = _user(db_session, "outcome-dup-sent@example.com")
    email = _generated_email(db_session, user, domain="outcome-dup-sent.test")

    _create(db_session, user, email.id, OutcomeEventType.SENT)

    with pytest.raises(ValidationError) as exc_info:
        _create(db_session, user, email.id, OutcomeEventType.SENT)

    assert "already marked as sent" in exc_info.value.user_message
    assert (
        db_session.query(Outcome)
        .filter(Outcome.generated_email_id == email.id)
        .count()
        == 1
    )


def test_create_non_sent_without_sent_raises_validation_error(
    db_session: Session,
):
    user = _user(db_session, "outcome-need-sent@example.com")
    email = _generated_email(db_session, user, domain="outcome-need-sent.test")

    with pytest.raises(ValidationError) as exc_info:
        _create(db_session, user, email.id, OutcomeEventType.REPLIED)

    assert "Mark this email as sent" in exc_info.value.user_message
    assert (
        db_session.query(Outcome)
        .filter(Outcome.generated_email_id == email.id)
        .count()
        == 0
    )


def test_create_sent_after_retract_succeeds(db_session: Session):
    """Retracted SENT no longer blocks a fresh SENT (partial unique index)."""
    user = _user(db_session, "outcome-resent@example.com")
    email = _generated_email(db_session, user, domain="outcome-resent.test")

    first = _create(db_session, user, email.id, OutcomeEventType.SENT)
    outcomes_service.retract_outcome(db_session, user, first.id)
    second = _create(db_session, user, email.id, OutcomeEventType.SENT)

    assert second.id != first.id
    assert second.voided is False
    assert first.voided is True
    listed = outcomes_service.list_outcomes(db_session, user)
    assert len(listed) == 1
    assert listed[0].id == second.id


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

    _create(db_session, alice, alice_email_a.id, OutcomeEventType.SENT)
    _create(db_session, alice, alice_email_b.id, OutcomeEventType.SENT)
    _create(db_session, alice, alice_email_b.id, OutcomeEventType.NO_RESPONSE)
    _create(db_session, bob, bob_email.id, OutcomeEventType.SENT)
    _create(db_session, bob, bob_email.id, OutcomeEventType.INTERVIEW)

    alice_all = outcomes_service.list_outcomes(db_session, alice)
    assert len(alice_all) == 3
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
    assert len(bob_all) == 2
    assert {row.event_type for row in bob_all} == {
        OutcomeEventType.SENT,
        OutcomeEventType.INTERVIEW,
    }


def test_retract_outcome_wrong_owner_raises_not_found(db_session: Session):
    owner = _user(db_session, "retract-owner@example.com")
    other = _user(db_session, "retract-other@example.com")
    email = _generated_email(db_session, owner, domain="retract-wrong-owner.test")

    outcome = _create(db_session, owner, email.id, OutcomeEventType.SENT)

    with pytest.raises(NotFoundError):
        outcomes_service.retract_outcome(db_session, other, outcome.id)

    db_session.refresh(outcome)
    assert outcome.voided is False


def test_retract_outcome_voids_and_excludes_from_list(db_session: Session):
    user = _user(db_session, "retract-success@example.com")
    email = _generated_email(db_session, user, domain="retract-success.test")

    outcome = _create(db_session, user, email.id, OutcomeEventType.SENT)
    assert outcome.voided is False
    # OutcomeOut exposes voided so retract (and create) responses confirm state.
    assert OutcomeOut.model_validate(outcome).voided is False
    assert len(outcomes_service.list_outcomes(db_session, user)) == 1

    retracted = outcomes_service.retract_outcome(db_session, user, outcome.id)

    assert retracted.id == outcome.id
    assert retracted.voided is True
    assert OutcomeOut.model_validate(retracted).voided is True
    assert outcomes_service.list_outcomes(db_session, user) == []
    # Row still exists in Postgres for audit — only the list path hides it.
    assert db_session.query(Outcome).filter(Outcome.id == outcome.id).one().voided is True


def test_retract_outcome_already_voided_is_idempotent(db_session: Session):
    """Retracting an already-voided outcome is a no-op success, not an error."""
    user = _user(db_session, "retract-idempotent@example.com")
    email = _generated_email(db_session, user, domain="retract-idempotent.test")

    outcome = _create(db_session, user, email.id, OutcomeEventType.SENT)
    first = outcomes_service.retract_outcome(db_session, user, outcome.id)
    second = outcomes_service.retract_outcome(db_session, user, outcome.id)

    assert first.voided is True
    assert second.voided is True
    assert first.id == second.id == outcome.id
    assert outcomes_service.list_outcomes(db_session, user) == []


def test_retract_sent_cascades_to_other_outcomes(db_session: Session):
    user = _user(db_session, "retract-cascade@example.com")
    email = _generated_email(db_session, user, domain="retract-cascade.test")

    sent = _create(db_session, user, email.id, OutcomeEventType.SENT)
    replied = _create(db_session, user, email.id, OutcomeEventType.REPLIED)
    interview = _create(db_session, user, email.id, OutcomeEventType.INTERVIEW)

    retracted = outcomes_service.retract_outcome(db_session, user, sent.id)

    assert retracted.voided is True
    db_session.refresh(replied)
    db_session.refresh(interview)
    assert replied.voided is True
    assert interview.voided is True
    assert outcomes_service.list_outcomes(db_session, user) == []


def test_retract_non_sent_does_not_cascade(db_session: Session):
    user = _user(db_session, "retract-no-cascade@example.com")
    email = _generated_email(db_session, user, domain="retract-no-cascade.test")

    sent = _create(db_session, user, email.id, OutcomeEventType.SENT)
    replied = _create(db_session, user, email.id, OutcomeEventType.REPLIED)

    retracted = outcomes_service.retract_outcome(db_session, user, replied.id)

    assert retracted.voided is True
    db_session.refresh(sent)
    assert sent.voided is False
    listed = outcomes_service.list_outcomes(db_session, user)
    assert len(listed) == 1
    assert listed[0].id == sent.id
