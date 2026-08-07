"""Analytics HTTP endpoints — thin router over ``services/analytics.py``."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsSummary
from app.services import analytics as analytics_service

router = APIRouter(tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsSummary:
    """Reply rate overall + by confidence tier + by eval-score bucket."""
    return analytics_service.get_reply_rate_summary(db, current_user)
