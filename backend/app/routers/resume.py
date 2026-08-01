"""Resume HTTP endpoints: upload, list, detail, and extract (auth required)."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.resume import ResumeOut
from app.services import extraction as extraction_service
from app.services import resume as resume_service

router = APIRouter(tags=["resumes"])


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeOut:
    return resume_service.create_resume_from_upload(db, current_user, file)


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResumeOut]:
    return resume_service.get_resumes_for_user(db, current_user)


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeOut:
    return resume_service.get_resume_by_id(db, current_user, resume_id)


@router.post("/{resume_id}/extract", response_model=ResumeOut)
async def extract_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeOut:
    """Re-runnable structured extraction — overwrites ``extracted_data``."""
    return await extraction_service.extract_resume(
        db, resume_id, current_user.id
    )
