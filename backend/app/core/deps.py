"""FastAPI dependencies: DB session and current-user resolution."""

from collections.abc import Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User

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

    JWT signature/expiry/token_type checks live in decode_access_token
    (security.py) — this dependency only loads the User row. Raises
    AuthenticationError on any failure (see exceptions.py and the
    central handler in main.py).
    """
    access = decode_access_token(token)

    user = db.query(User).filter(User.id == access.user_id).first()
    if user is None:
        raise AuthenticationError(
            detail=f"No user found for id={access.user_id}"
        )

    return user
