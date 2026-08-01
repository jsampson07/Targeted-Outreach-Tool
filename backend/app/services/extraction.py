"""User-triggered LLM structured extraction for resumes and job descriptions.

Separate retryable endpoints (not inline on upload) — re-running overwrite
``extracted_data``. Calls ``LLMClient`` only; never the Anthropic SDK directly
(ARCHITECTURE.md §3).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.llm.client import LLMClient
from app.llm.prompts import jd_extraction_prompt, resume_extraction_prompt
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ResumeExtraction
from app.services import job_description as job_description_service
from app.services import resume as resume_service


def _user_for_id(db: Session, user_id: int) -> User:
    """Resolve user_id to a User for ownership helpers that take User."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        # Callers pass an authenticated user_id; this is defensive only.
        raise NotFoundError(detail=f"User id={user_id} not found")
    return user


async def extract_resume(
    db: Session,
    resume_id: int,
    user_id: int,
    *,
    llm_client: LLMClient | None = None,
) -> Resume:
    """Run resume extraction and persist into ``extracted_data`` (overwrite)."""
    user = _user_for_id(db, user_id)
    resume = resume_service.get_resume_by_id(db, user, resume_id)
    client = llm_client or LLMClient()
    extraction = await client.complete(
        resume_extraction_prompt(resume.raw_text),
        ResumeExtraction,
    )
    resume.extracted_data = extraction.model_dump()
    db.commit()
    db.refresh(resume)
    return resume


async def extract_job_description(
    db: Session,
    jd_id: int,
    user_id: int,
    *,
    llm_client: LLMClient | None = None,
) -> JobDescription:
    """Run JD extraction and persist into ``extracted_data`` (overwrite)."""
    user = _user_for_id(db, user_id)
    jd = job_description_service.get_job_description_by_id(db, user, jd_id)
    client = llm_client or LLMClient()
    extraction = await client.complete(
        jd_extraction_prompt(jd.raw_text),
        JDExtraction,
    )
    jd.extracted_data = extraction.model_dump()
    db.commit()
    db.refresh(jd)
    return jd
