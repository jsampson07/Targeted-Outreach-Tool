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

# Standalone valediction phrases only — matched against a whole line after
# trimming whitespace and a single trailing comma/period. Substrings inside
# a longer sentence (e.g. "Thanks for your time.") must not match.
_CLOSING_PHRASES = frozenset(
    {
        "best",
        "best regards",
        "sincerely",
        "regards",
        "warm regards",
        "kind regards",
        "warmly",
        "thank you",
        "thanks",
    }
)


def _is_closing_line(line: str) -> bool:
    """True when ``line`` is a standalone closing phrase (not a sentence)."""
    s = line.strip()
    if s.endswith(",") or s.endswith("."):
        s = s[:-1]
    return s.strip().lower() in _CLOSING_PHRASES


def _strip_trailing_closing(body: str, candidate_name: str | None) -> str:
    """Remove a model-authored trailing sign-off before the programmatic append.

    Conservative: only the last 1–3 non-blank lines are considered, and a line
    is stripped only when it is an exact standalone valediction (optionally
    followed by a line equal to ``candidate_name``). Mid-sentence uses of
    "thanks"/"regards" are left alone.
    """
    lines = body.split("\n")

    end = len(lines) - 1
    while end >= 0 and lines[end].strip() == "":
        end -= 1
    if end < 0:
        return body

    # Last 1–3 non-blank line indices, bottom-to-top.
    window: list[int] = []
    j = end
    while j >= 0 and len(window) < 3:
        if lines[j].strip() != "":
            window.append(j)
        j -= 1

    strip: set[int] = set()
    idx = 0
    while idx < len(window):
        line_i = window[idx]
        line = lines[line_i]

        # window[0] is always the body's last non-blank line (from `end`), so a
        # trailing name-after-closing is always caught by the name-first branch
        # below — a forward "after" lookahead here would only ever see blanks.
        if _is_closing_line(line):
            strip.add(line_i)
            idx += 1
            continue

        if (
            candidate_name is not None
            and line.strip().lower() == candidate_name.strip().lower()
            and idx + 1 < len(window)
        ):
            prev_i = window[idx + 1]
            if _is_closing_line(lines[prev_i]) and line_i == prev_i + 1:
                strip.add(line_i)
                strip.add(prev_i)
                idx += 2
                continue

        # First non-matching line from the bottom — stop.
        break

    if not strip:
        return body

    new_lines = [ln for i, ln in enumerate(lines) if i not in strip]
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()
    return "\n".join(new_lines)


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

    # Strip any model-authored trailing sign-off the prompts failed to prevent,
    # then append the deterministic signature. Both steps run only on the final
    # draft after evaluate_with_retry — the judge still sees raw model output.
    cleaned_body = _strip_trailing_closing(
        final_email.body, resume_extraction.candidate_name
    )
    if resume_extraction.candidate_name:
        body = (
            f"{cleaned_body}\n\nBest regards,\n"
            f"{resume_extraction.candidate_name}"
        )
    else:
        body = f"{cleaned_body}\n\nBest regards,"

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
        and eval_result.gates.no_unprompted_gap_admission
    )

    row = GeneratedEmail(
        contact_id=contact_id,
        resume_id=resume_id,
        job_description_id=job_description_id,
        subject=final_email.subject,
        body=body,
        eval_score=eval_score,
        eval_breakdown=eval_result.model_dump(),
        match_data=match_data.model_dump(),
        gate_passed=gate_passed,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
