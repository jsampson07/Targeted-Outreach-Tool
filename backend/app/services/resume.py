"""Resume upload and retrieval: parse PDF/DOCX to text, persist raw_text only.

LLM structured extraction is Phase 3 — extracted_data is always None here.
"""

from io import BytesIO

from docx import Document
from fastapi import UploadFile
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeCreate

_MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2MB
_MIN_RAW_TEXT_CHARS = 50
_ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def parse_pdf(file_bytes: bytes) -> str:
    """Extract and join text from every page of a PDF."""
    reader = PdfReader(BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def parse_docx(file_bytes: bytes) -> str:
    """Extract and join all paragraph text from a DOCX file."""
    document = Document(BytesIO(file_bytes))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def create_resume_from_upload(
    db: Session, user: User, upload_file: UploadFile
) -> Resume:
    """Parse an uploaded PDF/DOCX and persist a Resume with raw_text only."""
    filename = upload_file.filename or ""
    lower_name = filename.lower()
    if not any(lower_name.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise ValidationError(
            detail=f"Rejected upload with unsupported filename={filename!r}",
            user_message="Only PDF and DOCX files are accepted.",
        )

    file_bytes = upload_file.file.read()
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise ValidationError(
            detail=f"Upload exceeded size limit: {len(file_bytes)} bytes",
            user_message="File too large",
        )

    try:
        if lower_name.endswith(".pdf"):
            raw_text = parse_pdf(file_bytes)
        else:
            raw_text = parse_docx(file_bytes)
    except Exception as exc:
        raise ValidationError(
            detail=f"Failed to parse resume file={filename!r}: {exc!r}",
            user_message=(
                "Couldn't read that file — it may be corrupted. "
                "Try exporting it again or using a different file."
            ),
        ) from exc

    raw_text = raw_text.strip()
    if len(raw_text) < _MIN_RAW_TEXT_CHARS:
        raise ValidationError(
            detail=(
                f"Extracted text too short ({len(raw_text)} chars) "
                f"from file={filename!r}"
            ),
            user_message=(
                "Couldn't extract readable text from that file — it may "
                "be a scanned image. Try a different file."
            ),
        )
    resume_in = ResumeCreate(raw_text=raw_text)
    resume = Resume(
        user_id=user.id,
        raw_text=resume_in.raw_text,
        extracted_data=None,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_resumes_for_user(db: Session, user: User) -> list[Resume]:
    """Return all resumes owned by the given user."""
    return (
        db.query(Resume)
        .filter(Resume.user_id == user.id)
        .order_by(Resume.created_at.desc())
        .all()
    )


def get_resume_by_id(db: Session, user: User, resume_id: int) -> Resume:
    """Fetch one resume by id AND user_id — no ownership leak via 403."""
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == user.id)
        .first()
    )
    if resume is None:
        raise NotFoundError(
            detail=f"Resume id={resume_id} not found for user_id={user.id}"
        )
    return resume
