"""Outcome HTTP endpoints: create, ownership-scoped list, and retract."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.outcome import OutcomeCreate, OutcomeOut
from app.services import outcomes as outcomes_service

router = APIRouter(tags=["outcomes"])


@router.post(
    "", response_model=OutcomeOut, status_code=status.HTTP_201_CREATED
)
def create_outcome(
    outcome_in: OutcomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutcomeOut:
    return outcomes_service.create_outcome(db, current_user, outcome_in)


@router.get("", response_model=list[OutcomeOut])
def list_outcomes(
    generated_email_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OutcomeOut]:
    return outcomes_service.list_outcomes(
        db, current_user, generated_email_id=generated_email_id
    )


@router.post("/{outcome_id}/retract", response_model=OutcomeOut)
def retract_outcome(
    outcome_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutcomeOut:
    """One-way soft-delete — sets voided=true. Idempotent if already voided."""
    return outcomes_service.retract_outcome(db, current_user, outcome_id)
