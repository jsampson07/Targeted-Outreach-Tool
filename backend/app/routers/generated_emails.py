"""Generated-email HTTP endpoint: match → generate → evaluate → persist."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.generated_email import GenerateEmailRequest, GeneratedEmailOut
from app.services.generated_emails import generate_and_persist_email

router = APIRouter(tags=["generated-emails"])


@router.post("", response_model=GeneratedEmailOut)
async def create_generated_email(
    body: GenerateEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GeneratedEmailOut:
    return await generate_and_persist_email(
        db,
        current_user,
        body.contact_id,
        body.resume_id,
        body.job_description_id,
    )
