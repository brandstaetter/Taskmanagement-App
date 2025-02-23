"""Authentication router."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from taskmanagement_app.auth.dependencies import (
    get_current_active_user,
    get_current_admin_user,
)
from taskmanagement_app.auth.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    get_password_hash,
)
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.db.base import get_db
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.token import Token

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class UserCreate(BaseModel):
    """User creation schema."""

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """User update schema."""

    password: str
    avatar_url: str | None = None


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
) -> Token:
    """Get access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin_user)],
) -> dict[str, str]:
    """Create a new user (admin only)."""
    if db.query(User).filter(User.email == user_create.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    db_user = User(
        email=user_create.email,
        hashed_password=get_password_hash(user_create.password),
    )
    db.add(db_user)
    db.commit()
    return {"message": "User created successfully"}


@router.put("/users/me")
async def update_user(
    user_update: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, str]:
    """Update current user's password and avatar."""
    current_user.hashed_password = get_password_hash(user_update.password)
    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url
    db.commit()
    return {"message": "User updated successfully"}


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    new_password: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin_user)],
) -> dict[str, str]:
    """Reset a user's password (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"message": "Password reset successfully"}
