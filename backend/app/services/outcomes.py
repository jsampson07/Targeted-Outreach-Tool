"""Append-only outcome event log — create, list, and retract, scoped to user.

Ownership of the referenced ``GENERATED_EMAILS`` row is verified via the
existing Resume-join helper (``get_generated_email_by_id``) on create;
``user_id`` on the Outcome row is then set from ``current_user.id`` directly.
Retract verifies ownership via ``Outcome.user_id`` (already denormalized).

CRITICAL DISCIPLINE: every read of OUTCOMES — current ``list_outcomes``, and
analytics (``services/analytics.py`` via ``list_outcomes``) — MUST go through
this module rather than a fresh ad-hoc query written elsewhere. That is what
keeps the ``voided=false`` filter from being silently forgotten by a future
read path. Do not query the ``Outcome`` model for reads outside this file.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.outcome import Outcome
from app.models.user import User
from app.schemas.outcome import OutcomeCreate
from app.services.generated_emails import get_generated_email_by_id


def create_outcome(
    db: Session, current_user: User, outcome_data: OutcomeCreate
) -> Outcome:
    """Insert one outcome event after verifying ownership of the email."""
    # Raises NotFoundError for missing or wrong-owner generated emails —
    # same non-distinguishing 404 as GET /generated-emails/{id}.
    get_generated_email_by_id(db, current_user, outcome_data.generated_email_id)

    outcome = Outcome(
        user_id=current_user.id,
        generated_email_id=outcome_data.generated_email_id,
        event_type=outcome_data.event_type,
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


def list_outcomes(
    db: Session,
    current_user: User,
    generated_email_id: int | None = None,
) -> list[Outcome]:
    """Return the caller's non-voided outcomes, optionally by generated_email_id.

    Voided rows remain in Postgres for audit but are never returned here.
    There is no include-voided query param in v1.
    """
    query = db.query(Outcome).filter(
        Outcome.user_id == current_user.id,
        Outcome.voided.is_(False),
    )
    if generated_email_id is not None:
        query = query.filter(Outcome.generated_email_id == generated_email_id)
    return query.order_by(Outcome.occurred_at.asc(), Outcome.id.asc()).all()


def retract_outcome(
    db: Session, current_user: User, outcome_id: int
) -> Outcome:
    """Soft-delete one outcome (voided=true). Idempotent if already voided.

    Ownership uses ``Outcome.user_id`` directly — no GeneratedEmail/Resume
    re-join. Missing or wrong-owner → NotFoundError (non-distinguishing 404).
    Already-voided → no-op success (idempotent), not an error.
    """
    outcome = (
        db.query(Outcome)
        .filter(Outcome.id == outcome_id, Outcome.user_id == current_user.id)
        .first()
    )
    if outcome is None:
        raise NotFoundError(
            detail=(
                f"Outcome id={outcome_id} not found for user_id={current_user.id}"
            )
        )
    if not outcome.voided:
        outcome.voided = True
        db.commit()
        db.refresh(outcome)
    return outcome
