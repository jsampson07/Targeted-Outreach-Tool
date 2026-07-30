"""End-to-end resume integration tests against real Postgres."""

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.resume import Resume

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES / "sample_resume.pdf"
SAMPLE_DOCX = FIXTURES / "sample_resume.docx"


def _signup(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = "secret-password",
):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )


def _auth_headers(client: TestClient, email: str, password: str = "secret-password") -> dict:
    signup = _signup(client, email=email, password=password)
    assert signup.status_code == 201
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


def _minimal_pdf_with_text(text: str) -> bytes:
    """Build a tiny PDF whose extractable text is exactly `text`."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        ),
        (
            f"4 0 obj<< /Length {len(stream)} >>stream\n".encode()
            + stream
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def test_upload_resume_happy_path_pdf(client: TestClient, db_session: Session):
    headers = _auth_headers(client, "uploader@example.com")
    response = client.post(
        "/resumes",
        headers=headers,
        files={"file": ("sample_resume.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["user_id"]
    assert "Jane Doe" in body["raw_text"]
    assert body["extracted_data"] is None
    assert "created_at" in body

    row = db_session.query(Resume).filter(Resume.id == body["id"]).first()
    assert row is not None
    assert row.extracted_data is None
    assert row.user_id == body["user_id"]


def test_upload_resume_happy_path_docx(client: TestClient):
    headers = _auth_headers(client, "docx-user@example.com")
    response = client.post(
        "/resumes",
        headers=headers,
        files={
            "file": (
                "sample_resume.docx",
                SAMPLE_DOCX.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["extracted_data"] is None
    assert "Python" in body["raw_text"]


def test_upload_rejects_non_pdf_docx(client: TestClient):
    headers = _auth_headers(client, "bad-ext@example.com")
    response = client.post(
        "/resumes",
        headers=headers,
        files={"file": ("notes.txt", b"plain text resume content here", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "ValidationError"


def test_upload_rejects_oversized_file(client: TestClient):
    headers = _auth_headers(client, "too-big@example.com")
    oversized = b"%PDF-1.4\n" + (b"x" * (2 * 1024 * 1024))
    response = client.post(
        "/resumes",
        headers=headers,
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "ValidationError"
    assert body["user_message"] == "File too large"


def test_upload_rejects_near_empty_extracted_text(client: TestClient):
    headers = _auth_headers(client, "empty-text@example.com")
    tiny_pdf = _minimal_pdf_with_text("hi")
    response = client.post(
        "/resumes",
        headers=headers,
        files={"file": ("emptyish.pdf", tiny_pdf, "application/pdf")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "ValidationError"
    assert "scanned image" in body["user_message"]


def test_list_resumes_returns_only_current_users(client: TestClient):
    alice_headers = _auth_headers(client, "alice-list@example.com")
    bob_headers = _auth_headers(client, "bob-list@example.com")

    alice_upload = client.post(
        "/resumes",
        headers=alice_headers,
        files={"file": ("alice.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    bob_upload = client.post(
        "/resumes",
        headers=bob_headers,
        files={"file": ("bob.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    assert alice_upload.status_code == 201
    assert bob_upload.status_code == 201
    alice_id = alice_upload.json()["id"]
    bob_id = bob_upload.json()["id"]

    alice_list = client.get("/resumes", headers=alice_headers)
    bob_list = client.get("/resumes", headers=bob_headers)

    assert alice_list.status_code == 200
    assert bob_list.status_code == 200
    alice_ids = {r["id"] for r in alice_list.json()}
    bob_ids = {r["id"] for r in bob_list.json()}
    assert alice_ids == {alice_id}
    assert bob_ids == {bob_id}
    assert bob_id not in alice_ids
    assert alice_id not in bob_ids


def test_get_resume_other_users_is_404_like_missing(client: TestClient):
    alice_headers = _auth_headers(client, "alice-get@example.com")
    bob_headers = _auth_headers(client, "bob-get@example.com")

    upload = client.post(
        "/resumes",
        headers=alice_headers,
        files={"file": ("alice.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201
    alice_resume_id = upload.json()["id"]

    other_users = client.get(f"/resumes/{alice_resume_id}", headers=bob_headers)
    missing = client.get("/resumes/999999999", headers=bob_headers)

    assert other_users.status_code == 404
    assert missing.status_code == 404
    assert other_users.json()["error_code"] == "NotFoundError"
    assert missing.json()["error_code"] == "NotFoundError"
    assert other_users.json()["user_message"] == missing.json()["user_message"]


def test_get_own_resume_happy_path(client: TestClient):
    headers = _auth_headers(client, "owner-get@example.com")
    upload = client.post(
        "/resumes",
        headers=headers,
        files={"file": ("mine.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    resume_id = upload.json()["id"]

    response = client.get(f"/resumes/{resume_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == resume_id
    assert body["extracted_data"] is None


def test_resume_routes_require_auth(client: TestClient):
    unauth_post = client.post(
        "/resumes",
        files={"file": ("sample.pdf", SAMPLE_PDF.read_bytes(), "application/pdf")},
    )
    unauth_list = client.get("/resumes")
    unauth_detail = client.get("/resumes/1")

    assert unauth_post.status_code == 401
    assert unauth_list.status_code == 401
    assert unauth_detail.status_code == 401
