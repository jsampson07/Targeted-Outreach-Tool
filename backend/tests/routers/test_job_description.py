"""End-to-end job-description integration tests against real Postgres."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job_description import JobDescription


@pytest.fixture
def company(db_session: Session) -> Company:
    """Insert a Company row directly — no company-creation API exists yet."""
    row = Company(name="Example Co", domain="example.com")
    db_session.add(row)
    db_session.flush()
    return row


def _signup(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = "secret-password",
):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )


def _auth_headers(
    client: TestClient, email: str, password: str = "secret-password"
) -> dict:
    signup = _signup(client, email=email, password=password)
    assert signup.status_code == 201
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


def test_create_job_description_happy_path(
    client: TestClient, db_session: Session, company: Company
):
    headers = _auth_headers(client, "jd-uploader@example.com")
    response = client.post(
        "/job-descriptions",
        headers=headers,
        json={
            "company_id": company.id,
            "role_title": "Software Engineer",
            "raw_text": "Build APIs and ship features with Python.",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["user_id"]
    assert body["company_id"] == company.id
    assert body["role_title"] == "Software Engineer"
    assert body["raw_text"] == "Build APIs and ship features with Python."
    assert body["extracted_data"] is None
    assert "created_at" in body

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert body["user_id"] == me.json()["id"]

    row = (
        db_session.query(JobDescription)
        .filter(JobDescription.id == body["id"])
        .first()
    )
    assert row is not None
    assert row.extracted_data is None
    assert row.user_id == body["user_id"]


def test_create_job_description_unknown_company_is_404(
    client: TestClient, company: Company
):
    headers = _auth_headers(client, "missing-co@example.com")
    response = client.post(
        "/job-descriptions",
        headers=headers,
        json={
            "company_id": 999999999,
            "role_title": "Engineer",
            "raw_text": "Some non-empty job description text.",
        },
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "NotFoundError"


def test_create_job_description_rejects_empty_raw_text(
    client: TestClient, company: Company
):
    headers = _auth_headers(client, "empty-jd@example.com")
    for raw_text in ("", "   ", "\n\t  "):
        response = client.post(
            "/job-descriptions",
            headers=headers,
            json={
                "company_id": company.id,
                "role_title": "Engineer",
                "raw_text": raw_text,
            },
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "ValidationError"


def test_create_job_description_requires_auth(
    client: TestClient, company: Company
):
    response = client.post(
        "/job-descriptions",
        json={
            "company_id": company.id,
            "role_title": "Engineer",
            "raw_text": "Some non-empty job description text.",
        },
    )
    assert response.status_code == 401


def test_two_users_same_company_create_distinct_rows(
    client: TestClient, db_session: Session, company: Company
):
    alice_headers = _auth_headers(client, "alice-jd@example.com")
    bob_headers = _auth_headers(client, "bob-jd@example.com")
    payload = {
        "company_id": company.id,
        "role_title": "Backend Engineer",
        "raw_text": "Identical pasted posting text for both users.",
    }

    alice_resp = client.post(
        "/job-descriptions", headers=alice_headers, json=payload
    )
    bob_resp = client.post(
        "/job-descriptions", headers=bob_headers, json=payload
    )
    assert alice_resp.status_code == 201
    assert bob_resp.status_code == 201

    alice_body = alice_resp.json()
    bob_body = bob_resp.json()
    assert alice_body["id"] != bob_body["id"]
    assert alice_body["user_id"] != bob_body["user_id"]

    alice_me = client.get("/auth/me", headers=alice_headers).json()
    bob_me = client.get("/auth/me", headers=bob_headers).json()
    assert alice_body["user_id"] == alice_me["id"]
    assert bob_body["user_id"] == bob_me["id"]

    rows = (
        db_session.query(JobDescription)
        .filter(JobDescription.company_id == company.id)
        .all()
    )
    assert len(rows) == 2
    assert {r.id for r in rows} == {alice_body["id"], bob_body["id"]}
    assert {r.user_id for r in rows} == {
        alice_body["user_id"],
        bob_body["user_id"],
    }
