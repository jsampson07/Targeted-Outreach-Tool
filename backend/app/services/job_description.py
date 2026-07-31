"""Job description submission: persist pasted plain text with company + role.

LLM structured extraction is Phase 3 — extracted_data is always None here.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.company import Company
from app.models.job_description import JobDescription
from app.models.user import User
from app.schemas.job_description import JobDescriptionCreate


def create_job_description(
    db: Session, user: User, jd_in: JobDescriptionCreate
) -> JobDescription:
    """Validate company + non-empty text, then persist a JobDescription row."""
    company = db.query(Company).filter(Company.id == jd_in.company_id).first()
    if company is None:
        raise NotFoundError(
            detail=f"Company id={jd_in.company_id} not found"
        )

    raw_text = jd_in.raw_text.strip()
    if not raw_text:
        raise ValidationError(
            detail="Job description raw_text was empty or whitespace-only",
            user_message="Job description text cannot be empty.",
        )

    jd = JobDescription(
        user_id=user.id,
        company_id=jd_in.company_id,
        role_title=jd_in.role_title,
        raw_text=raw_text,
        extracted_data=None,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd


def get_job_description_by_id(db: Session, jd_id: int) -> JobDescription:
    """Plain lookup by id — for internal use by other services, not the router."""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if jd is None:
        raise NotFoundError(detail=f"JobDescription id={jd_id} not found")
    return jd
