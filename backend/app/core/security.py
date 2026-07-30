"""Password hashing and JWT / refresh-token utilities.

Pure crypto helpers only — no DB or session imports. Persisting and
looking up RefreshToken rows belongs in the auth service layer.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


@dataclass(frozen=True)
class AccessTokenPayload:
    """Validated access-token claims needed by callers (e.g. deps)."""

    user_id: int


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns a UTF-8 string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the bcrypt hashed_password."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Encode a short-lived access JWT for the given user id.

    Claims: sub (stringified user id), exp, iat, token_type="access".
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_delta,
        "token_type": "access",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> AccessTokenPayload:
    """Verify signature/expiry/token_type and return the access payload.

    Any failure mode (bad signature, expired, malformed, wrong
    token_type, missing/invalid sub) raises AuthenticationError — never
    a raw PyJWT exception.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError(detail=f"JWT decode failed: {exc}") from exc

    if payload.get("token_type") != "access":
        raise AuthenticationError(
            detail=(
                f"Unexpected token_type: {payload.get('token_type')!r} "
                "(expected 'access')"
            )
        )

    sub = payload.get("sub")
    if sub is None:
        raise AuthenticationError(detail="Access token missing sub claim")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError(
            detail=f"Access token sub is not an int-compatible string: {sub!r}"
        ) from exc

    return AccessTokenPayload(user_id=user_id)


def generate_refresh_token() -> str:
    """Return a cryptographically secure opaque refresh token (not a JWT)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest of a refresh token — deterministic for indexed lookup.

    Must stay deterministic (not bcrypt): DATA_MODEL.md §2.9 stores
    token_hash with a unique index so a presented token is looked up via
    WHERE token_hash = hash(token). Bcrypt is salted/non-deterministic and
    cannot support that equality lookup.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expires_at() -> datetime:
    """UTC datetime when a newly issued refresh token should expire."""
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
