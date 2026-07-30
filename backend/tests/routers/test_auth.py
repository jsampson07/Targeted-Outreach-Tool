"""End-to-end auth integration tests against real Postgres."""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_refresh_token
from app.models.refresh_token import RefreshToken
from app.models.user import User


def _signup(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = "secret-password",
):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )


def test_signup_happy_path(client: TestClient, db_session: Session):
    response = _signup(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    user = db_session.query(User).filter(User.email == "alice@example.com").first()
    assert user is not None
    assert user.password_hash != "secret-password"


def test_signup_duplicate_email_returns_409(client: TestClient):
    assert _signup(client).status_code == 201
    response = _signup(client)
    assert response.status_code == 409
    assert response.json()["error_code"] == "ConflictError"
    assert "user_message" in response.json()


def test_login_happy_path(client: TestClient):
    _signup(client)
    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "secret-password"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_failures_share_user_message(client: TestClient):
    _signup(client)

    wrong_password = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    nonexistent = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "secret-password"},
    )

    assert wrong_password.status_code == 401
    assert nonexistent.status_code == 401
    assert wrong_password.json()["user_message"] == nonexistent.json()["user_message"]


def test_refresh_happy_path_echoes_same_refresh_token(client: TestClient):
    signup = _signup(client).json()
    old_access = signup["access_token"]
    refresh_token = signup["refresh_token"]

    refreshed = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["refresh_token"] == refresh_token
    assert body["access_token"]
    assert body["token_type"] == "bearer"

    # Newly issued access token is usable.
    me_new = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me_new.status_code == 200

    # Old access token remains independently valid (stateless JWT).
    me_old = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {old_access}"},
    )
    assert me_old.status_code == 200


def test_refresh_unknown_token_returns_401(client: TestClient):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "not-a-real-refresh-token"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "AuthenticationError"


def test_refresh_revoked_token_returns_401(client: TestClient, db_session: Session):
    signup = _signup(client).json()
    refresh_token = signup["refresh_token"]

    row = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        .first()
    )
    assert row is not None
    row.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


def test_refresh_expired_token_returns_401(client: TestClient, db_session: Session):
    signup = _signup(client).json()
    refresh_token = signup["refresh_token"]

    row = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        .first()
    )
    assert row is not None
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


def test_logout_revokes_token_then_refresh_fails(client: TestClient):
    signup = _signup(client).json()
    refresh_token = signup["refresh_token"]

    logout = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 204

    refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh.status_code == 401


def test_logout_is_idempotent(client: TestClient):
    signup = _signup(client).json()
    refresh_token = signup["refresh_token"]

    first = client.post("/auth/logout", json={"refresh_token": refresh_token})
    second = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert first.status_code == 204
    assert second.status_code == 204


def test_me_without_authorization_returns_401(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_with_valid_access_token(client: TestClient):
    signup = _signup(client, email="bob@example.com").json()
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {signup['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert "id" in body
    assert "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_me_with_expired_access_token_returns_401(client: TestClient):
    signup = _signup(client).json()
    settings = get_settings()
    payload = jwt.decode(
        signup["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    expired = jwt.encode(
        {
            "sub": payload["sub"],
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "token_type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401


def test_me_with_tampered_access_token_returns_401(client: TestClient):
    signup = _signup(client).json()
    tampered = signup["access_token"][:-4] + "xxxx"
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert response.status_code == 401
