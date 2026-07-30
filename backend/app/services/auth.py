"""Auth business logic: users, credential checks, and token pairs.

Routers stay thin — call these functions, return the result. Persistence
and hashing live here; pure crypto helpers live in app.core.security.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPairOut
from app.schemas.user import UserCreate

_AUTH_FAILURE_MESSAGE = "Incorrect email or password"


def create_user(db: Session, user_in: UserCreate) -> User:
    """Hash the password and persist a new user.

    Raises ConflictError if the email is already registered (409 — the
    request was well-formed but collided with existing state).
    """
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing is not None:
        raise ConflictError(
            detail=f"Signup attempted with existing email={user_in.email!r}"
        )

    user = User(
        email=user_in.email,
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify email+password and return the User.

    Uses the same user-facing message for "email missing" and "wrong
    password" so the response cannot be used for account enumeration.
    """
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError(
            detail=f"Failed login for email={email!r}",
            user_message=_AUTH_FAILURE_MESSAGE,
        )
    return user


def issue_token_pair(db: Session, user: User) -> TokenPairOut:
    """Create an access JWT and a new refresh-token row; return TokenPairOut.

    The response carries the raw (unhashed) refresh token. Only the hash
    is stored — never return or log the hash as if it were the token.
    """
    access_token = create_access_token(user_id=user.id)
    raw_refresh = generate_refresh_token()

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expires_at(),
        )
    )
    db.commit()

    return TokenPairOut(
        access_token=access_token,
        refresh_token=raw_refresh,
    )


def refresh_access_token(db: Session, presented_refresh_token: str) -> TokenPairOut:
    """Validate a refresh token and issue a new access token.

    No rotation: the same refresh token is echoed back unchanged. Raises
    AuthenticationError if the token is unknown, revoked, or expired.
    """
    token_hash = hash_refresh_token(presented_refresh_token)
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    now = datetime.now(timezone.utc)
    if (
        row is None
        or row.revoked_at is not None
        or row.expires_at <= now
    ):
        raise AuthenticationError(
            detail="Refresh token missing, revoked, or expired"
        )

    return TokenPairOut(
        access_token=create_access_token(user_id=row.user_id),
        refresh_token=presented_refresh_token,
    )


def revoke_refresh_token(db: Session, presented_refresh_token: str) -> None:
    """Mark a refresh token revoked. Idempotent — unknown or already-revoked
    tokens succeed silently (no enumeration signal).
    """
    token_hash = hash_refresh_token(presented_refresh_token)
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )
    if row is None or row.revoked_at is not None:
        return

    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
