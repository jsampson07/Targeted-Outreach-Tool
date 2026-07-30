"""Unit tests for app.schemas — UserCreate/UserOut and TokenPairOut."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.auth import TokenPairOut
from app.schemas.user import UserCreate, UserOut


def test_user_create_accepts_valid_email_and_password():
    user = UserCreate(email="alice@example.com", password="secret")
    assert user.email == "alice@example.com"
    assert user.password == "secret"


def test_user_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="secret")


def test_user_out_from_attributes():
    orm_stand_in = SimpleNamespace(
        id=7,
        email="bob@example.com",
        created_at=datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc),
        password_hash="should-not-appear",
    )
    out = UserOut.model_validate(orm_stand_in)
    assert out.id == 7
    assert out.email == "bob@example.com"
    assert out.created_at == datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)
    assert not hasattr(out, "password_hash")


def test_token_pair_out_defaults_token_type_to_bearer():
    pair = TokenPairOut(access_token="access", refresh_token="refresh")
    assert pair.token_type == "bearer"


def test_token_pair_out_rejects_non_bearer_token_type():
    with pytest.raises(ValidationError):
        TokenPairOut(
            access_token="access",
            refresh_token="refresh",
            token_type="mac",
        )
