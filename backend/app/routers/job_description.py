"""Job description HTTP endpoints: plain-text paste submission (auth required)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.job_description import JobDescriptionCreate, JobDescriptionOut
from app.services import job_description as job_description_service

router = APIRouter(tags=["job-descriptions"])


@router.post(
    "", response_model=JobDescriptionOut, status_code=status.HTTP_201_CREATED
)
def create_job_description(
    jd_in: JobDescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionOut:
    return job_description_service.create_job_description(
        db, current_user, jd_in
    )
