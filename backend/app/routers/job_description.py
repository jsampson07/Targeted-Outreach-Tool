"""Job description HTTP endpoints: paste submission, detail, extract (auth required)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.job_description import JobDescriptionCreate, JobDescriptionOut
from app.services import extraction as extraction_service
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


@router.get("/{jd_id}", response_model=JobDescriptionOut)
def get_job_description(
    jd_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionOut:
    """Fetch one JD by id — ownership-filtered; missing/wrong-owner both 404."""
    return job_description_service.get_job_description_by_id(
        db, current_user, jd_id
    )


@router.post("/{jd_id}/extract", response_model=JobDescriptionOut)
async def extract_job_description(
    jd_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionOut:
    """Re-runnable structured extraction — overwrites ``extracted_data``."""
    return await extraction_service.extract_job_description(
        db, jd_id, current_user.id
    )
