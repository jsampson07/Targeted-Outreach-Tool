"""Orchestrate match → generate → evaluate → persist a GENERATED_EMAILS row.

DB-touching caller of the pure LLM services in ``matching.py``,
``email_generation.py``, and ``eval.py``. Always INSERTs a new row — never
overwrites an existing (contact, resume, JD) triple — so future OUTCOMES
rows retain a stable FK target.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.company import Company
from app.models.contact import Contact
from app.models.generated_email import GeneratedEmail
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ResumeExtraction
from app.services import job_description as job_description_service
from app.services import resume as resume_service
from app.services.email_generation import generate_email
from app.services.eval import evaluate_with_retry
from app.services.matching import generate_match_data


def get_generated_email_by_id(
    db: Session, user: User, generated_email_id: int
) -> GeneratedEmail:
    """Fetch one generated email by id, scoped to the caller's resumes.

    ``GENERATED_EMAILS`` has no ``user_id`` column — ownership is established
    by joining to ``RESUMES`` and filtering on ``Resume.user_id``. Safe because
    ``generate_and_persist_email`` only ever writes rows whose resume and JD
    were both loaded through ownership-filtered helpers for the same user.
    """
    row = (
        db.query(GeneratedEmail)
        .join(Resume, GeneratedEmail.resume_id == Resume.id)
        .filter(
            GeneratedEmail.id == generated_email_id,
            Resume.user_id == user.id,
        )
        .first()
    )
    if row is None:
        raise NotFoundError(
            detail=(
                f"GeneratedEmail id={generated_email_id} "
                f"not found for user_id={user.id}"
            )
        )
    return row


async def generate_and_persist_email(
    db: Session,
    current_user: User,
    contact_id: int,
    resume_id: int,
    job_description_id: int,
) -> GeneratedEmail:
    """Run the full generation loop and persist a new GeneratedEmail row."""
    # Cheap ownership/existence checks before any LLM call.
    resume = resume_service.get_resume_by_id(db, current_user, resume_id)
    jd = job_description_service.get_job_description_by_id(
        db, current_user, job_description_id
    )

    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if contact is None:
        raise NotFoundError(detail=f"Contact id={contact_id} not found")

    if resume.extracted_data is None:
        raise ValidationError(
            detail=f"Resume id={resume_id} has extracted_data=None",
            user_message=(
                "Resume must be extracted before generating an email. "
                f"Run extraction on resume id={resume_id} first."
            ),
        )
    if jd.extracted_data is None:
        raise ValidationError(
            detail=(
                f"JobDescription id={job_description_id} has extracted_data=None"
            ),
            user_message=(
                "Job description must be extracted before generating an email. "
                f"Run extraction on job description id={job_description_id} first."
            ),
        )

    company = (
        db.query(Company).filter(Company.id == contact.company_id).first()
    )
    if company is None:
        raise NotFoundError(
            detail=f"Company id={contact.company_id} not found"
        )

    if contact.company_id != jd.company_id:
        raise ValidationError(
            detail=(
                f"Contact id={contact_id} company_id={contact.company_id} "
                f"does not match JobDescription id={job_description_id} "
                f"company_id={jd.company_id}"
            ),
            user_message=(
                "Contact and job description must belong to the same company. "
                f"Contact is tied to company_id={contact.company_id}; "
                f"job description is tied to company_id={jd.company_id}."
            ),
        )

    resume_extraction = ResumeExtraction.model_validate(resume.extracted_data)
    jd_extraction = JDExtraction.model_validate(jd.extracted_data)

    match_data = await generate_match_data(resume_extraction, jd_extraction)
    draft = await generate_email(
        contact.name,
        contact.title,
        company.name,
        jd.role_title,
        match_data,
    )
    final_email, eval_result = await evaluate_with_retry(
        draft,
        match_data,
        contact.name,
        contact.title,
        company.name,
        jd.role_title,
    )

    dims = eval_result.dimensions
    eval_score = (
        dims.role_company_specificity
        + dims.relevance_alignment
        + dims.tone_professionalism
        + dims.conciseness
        + dims.clear_cta
    ) / 5.0
    gate_passed = (
        eval_result.gates.no_unsupported_claims
        and eval_result.gates.correct_contact_name_used
    )

    row = GeneratedEmail(
        contact_id=contact_id,
        resume_id=resume_id,
        job_description_id=job_description_id,
        subject=final_email.subject,
        body=final_email.body,
        eval_score=eval_score,
        eval_breakdown=eval_result.model_dump(),
        match_data=match_data.model_dump(),
        gate_passed=gate_passed,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
