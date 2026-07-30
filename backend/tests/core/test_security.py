"""Unit tests for app.core.security — password hashing, JWT, refresh tokens."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)


def test_hash_password_verify_round_trip():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", hashed) is False


def test_create_and_decode_access_token_round_trip():
    token = create_access_token(user_id=42)
    payload = decode_access_token(token)
    assert payload.user_id == 42


def test_expired_access_token_is_rejected():
    token = create_access_token(user_id=1, expires_delta=timedelta(seconds=-1))
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_non_access_token_type_is_rejected():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "1",
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "token_type": "refresh",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_tampered_access_token_is_rejected():
    token = create_access_token(user_id=7)
    # Flip one character in the signature segment (last of three JWT parts).
    header_payload, signature = token.rsplit(".", 1)
    flipped = "A" if signature[0] != "A" else "B"
    tampered = f"{header_payload}.{flipped}{signature[1:]}"
    with pytest.raises(AuthenticationError):
        decode_access_token(tampered)


def test_hash_refresh_token_is_deterministic_and_distinct():
    token_a = "opaque-refresh-token-aaa"
    token_b = "opaque-refresh-token-bbb"
    assert hash_refresh_token(token_a) == hash_refresh_token(token_a)
    assert hash_refresh_token(token_a) != hash_refresh_token(token_b)


def test_generate_refresh_token_produces_distinct_values():
    assert generate_refresh_token() != generate_refresh_token()


def test_refresh_token_expires_at_is_in_the_future():
    settings = get_settings()
    before = datetime.now(timezone.utc)
    expires = refresh_token_expires_at()
    after = datetime.now(timezone.utc)
    expected_min = before + timedelta(days=settings.refresh_token_expire_days)
    expected_max = after + timedelta(days=settings.refresh_token_expire_days)
    assert expected_min <= expires <= expected_max
