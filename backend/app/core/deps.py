# Destination in repo: backend/app/core/deps.py
#
# Requires: pip install python-jose[cryptography]
# (SessionLocal, User, and Settings are assumed to already exist per the
# locked db/models/config structure — not created in this pass.)

from collections.abc import Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.db.session import SessionLocal
from app.models.user import User

settings = get_settings()

# tokenUrl points at the login route that issues the access token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[Session, None, None]:
    """Yields a request-scoped SQLAlchemy session, closed after the request
    finishes regardless of success or failure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decodes and validates the access token, then loads the user.

    Raises AuthenticationError (a domain exception, not HTTPException
    directly) on any failure — see exceptions.py and the central handler
    in main.py for why that translation stays centralized rather than
    happening ad hoc here.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AuthenticationError(
            detail=f"JWT decode failed: {exc}"
        ) from exc

    user_id = payload.get("sub")
    token_type = payload.get("type")

    # "type" distinguishes access tokens from refresh tokens sharing the
    # same secret — without this check, a refresh token could be replayed
    # as if it were a valid access token.
    if user_id is None or token_type != "access":
        raise AuthenticationError(
            detail=f"Unexpected token payload: sub={user_id!r}, type={token_type!r}"
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise AuthenticationError(detail=f"No user found for id={user_id}")

    return user
