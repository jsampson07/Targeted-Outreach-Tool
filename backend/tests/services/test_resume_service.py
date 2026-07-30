"""Unit tests for resume PDF/DOCX parsing (no HTTP / DB)."""

from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.services.resume import parse_docx, parse_pdf

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES / "sample_resume.pdf"
SAMPLE_DOCX = FIXTURES / "sample_resume.docx"


def test_parse_pdf_extracts_readable_text():
    text = parse_pdf(SAMPLE_PDF.read_bytes())
    assert "Jane Doe" in text
    assert "Python" in text
    assert len(text.strip()) >= 50


def test_parse_docx_extracts_readable_text():
    text = parse_docx(SAMPLE_DOCX.read_bytes())
    assert "Jane Doe" in text
    assert "FastAPI" in text
    assert len(text.strip()) >= 50


def test_parse_pdf_corrupt_file_raises():
    with pytest.raises(Exception):
        parse_pdf(b"this is not a pdf file at all")


def test_parse_docx_corrupt_file_raises():
    with pytest.raises(Exception):
        parse_docx(b"this is not a docx file at all")


def test_create_resume_from_upload_wraps_corrupt_parse_as_validation_error():
    """Service-level: parser exceptions become ValidationError with plain copy."""
    from io import BytesIO
    from unittest.mock import MagicMock

    from app.services.resume import create_resume_from_upload

    upload = MagicMock()
    upload.filename = "broken.pdf"
    upload.file = BytesIO(b"%PDF-1.4 definitely-corrupt")

    with pytest.raises(ValidationError) as exc_info:
        create_resume_from_upload(db=MagicMock(), user=MagicMock(id=1), upload_file=upload)

    assert "Couldn't read that file" in exc_info.value.user_message

