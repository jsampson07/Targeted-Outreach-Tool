"""Auth HTTP endpoints: signup, login, refresh, logout, and /me."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPairOut
from app.schemas.user import UserCreate, UserOut
from app.services import auth as auth_service

router = APIRouter(tags=["auth"])


@router.post("/signup", response_model=TokenPairOut, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, db: Session = Depends(get_db)) -> TokenPairOut:
    user = auth_service.create_user(db, user_in)
    return auth_service.issue_token_pair(db, user)


@router.post("/login", response_model=TokenPairOut)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenPairOut:
    user = auth_service.authenticate_user(db, body.email, body.password)
    return auth_service.issue_token_pair(db, user)


@router.post("/refresh", response_model=TokenPairOut)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPairOut:
    return auth_service.refresh_access_token(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    auth_service.revoke_refresh_token(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
