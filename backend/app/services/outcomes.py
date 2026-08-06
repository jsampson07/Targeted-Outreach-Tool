"""Append-only outcome event log — create and list, scoped to current user.

Ownership of the referenced ``GENERATED_EMAILS`` row is verified via the
existing Resume-join helper (``get_generated_email_by_id``); ``user_id`` on
the Outcome row is then set from ``current_user.id`` directly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

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
    """Return the caller's outcomes, optionally filtered by generated_email_id."""
    query = db.query(Outcome).filter(Outcome.user_id == current_user.id)
    if generated_email_id is not None:
        query = query.filter(Outcome.generated_email_id == generated_email_id)
    return query.order_by(Outcome.occurred_at.asc(), Outcome.id.asc()).all()
