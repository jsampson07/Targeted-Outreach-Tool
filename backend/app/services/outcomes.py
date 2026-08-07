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

Create-time gates (app-level, backed by a partial unique index for SENT):
- At most one non-voided SENT per ``generated_email_id``.
- Non-SENT event types require an existing non-voided SENT first.

Retract cascade: voiding a non-voided SENT also voids every other non-voided
outcome for that email in the same transaction. Non-SENT retract is local.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import OutcomeEventType
from app.core.exceptions import NotFoundError, ValidationError
from app.models.outcome import Outcome
from app.models.user import User
from app.schemas.outcome import OutcomeCreate
from app.services.generated_emails import get_generated_email_by_id

_ALREADY_SENT_USER_MESSAGE = (
    "This email is already marked as sent. Retract the existing log first."
)
_SENT_REQUIRED_USER_MESSAGE = (
    "Mark this email as sent before logging this outcome."
)


def create_outcome(
    db: Session, current_user: User, outcome_data: OutcomeCreate
) -> Outcome:
    """Insert one outcome event after verifying ownership of the email.

    Enforces the SENT gate before insert; the partial unique index
    ``uq_outcomes_generated_email_id_nonvoided_sent`` is a race backstop.
    """
    # Raises NotFoundError for missing or wrong-owner generated emails —
    # same non-distinguishing 404 as GET /generated-emails/{id}.
    get_generated_email_by_id(db, current_user, outcome_data.generated_email_id)

    existing = list_outcomes(
        db, current_user, generated_email_id=outcome_data.generated_email_id
    )
    has_nonvoided_sent = any(
        row.event_type == OutcomeEventType.SENT for row in existing
    )

    if outcome_data.event_type == OutcomeEventType.SENT:
        if has_nonvoided_sent:
            raise ValidationError(
                detail=(
                    "Non-voided SENT already exists for "
                    f"generated_email_id={outcome_data.generated_email_id}"
                ),
                user_message=_ALREADY_SENT_USER_MESSAGE,
            )
    elif not has_nonvoided_sent:
        raise ValidationError(
            detail=(
                f"No non-voided SENT for generated_email_id="
                f"{outcome_data.generated_email_id}; cannot log "
                f"{outcome_data.event_type.value}"
            ),
            user_message=_SENT_REQUIRED_USER_MESSAGE,
        )

    outcome = Outcome(
        user_id=current_user.id,
        generated_email_id=outcome_data.generated_email_id,
        event_type=outcome_data.event_type,
    )
    db.add(outcome)
    try:
        db.commit()
    except IntegrityError as exc:
        # Race backstop: two near-simultaneous SENT inserts both passed the
        # app-level check before either committed. Translate to ValidationError
        # — do not leak IntegrityError / 500 to the client.
        db.rollback()
        if outcome_data.event_type == OutcomeEventType.SENT:
            raise ValidationError(
                detail=(
                    "Unique non-voided SENT constraint violated for "
                    f"generated_email_id={outcome_data.generated_email_id} "
                    "(likely a concurrent insert)"
                ),
                user_message=_ALREADY_SENT_USER_MESSAGE,
            ) from exc
        raise
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

    When retracting a non-voided SENT, also void every other non-voided
    outcome for the same ``generated_email_id`` in this transaction.
    Retracting a non-SENT row does not cascade.
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
        if outcome.event_type == OutcomeEventType.SENT:
            # Includes the SENT row itself — one pass voids the whole funnel
            # for this email. Reads go through list_outcomes (CRITICAL DISCIPLINE).
            to_void = list_outcomes(
                db,
                current_user,
                generated_email_id=outcome.generated_email_id,
            )
            for row in to_void:
                row.voided = True
        else:
            outcome.voided = True
        db.commit()
        db.refresh(outcome)
    return outcome
