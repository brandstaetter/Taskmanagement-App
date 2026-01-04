from datetime import datetime, timezone
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import verify_access_token, verify_not_superadmin
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.core.security import verify_password
from taskmanagement_app.crud.user import (
    change_user_password as crud_change_user_password,
)
from taskmanagement_app.crud.user import (
    get_user_by_email,
)
from taskmanagement_app.crud.user import update_user_avatar as crud_update_user_avatar
from taskmanagement_app.db.models.user import User
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.user import User as UserSchema
from taskmanagement_app.schemas.user import (
    UserAvatarUpdate,
    UserPasswordChange,
    UserPasswordReset,
)

router = APIRouter()


def get_current_user_for_me(
    payload: dict[str, Any] = Depends(verify_access_token),
    db: Session = Depends(get_db),
) -> Union[User, dict[str, Any]]:
    """Return the authenticated user from the access token payload for GET /me."""
    subject = payload.get("sub")
    role = payload.get("role")

    # Handle superadmin case
    if role == "superadmin" or subject == get_settings().ADMIN_USERNAME:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        return {
            "id": 0,  # Superadmin doesn't have a DB record
            "email": f"{settings.ADMIN_USERNAME}@example.com",  # Make it a valid email
            "is_active": True,
            "is_admin": True,
            "is_superadmin": True,
            "avatar_url": None,
            "last_login": None,
            "created_at": now,
            "updated_at": now,
        }

    # Handle regular users
    if not subject:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = get_user_by_email(db, email=subject)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return user


def get_current_user(
    payload: dict[str, Any] = Depends(verify_not_superadmin),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user from the access token payload."""
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = get_user_by_email(db, email=email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return user


@router.get("/me", response_model=UserSchema)
def get_current_user_info(
    current_user: Union[User, dict[str, Any]] = Depends(get_current_user_for_me),
) -> UserSchema:
    """Get the current user's information."""
    if isinstance(current_user, dict):
        # Superadmin case - already has all fields including is_superadmin
        return UserSchema.model_validate(current_user)
    else:
        # Regular user case - add is_superadmin field dynamically
        user_dict = {
            "id": current_user.id,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_admin": current_user.is_admin,
            "is_superadmin": False,  # Regular users are never superadmin
            "avatar_url": current_user.avatar_url,
            "last_login": current_user.last_login,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at,
        }
        return UserSchema.model_validate(user_dict)


@router.put("/me/password", response_model=UserSchema)
def change_password(
    password_data: UserPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserSchema:
    """Change the current user's password."""
    if not verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    updated = crud_change_user_password(
        db,
        user_id=current_user.id,
        password_data=UserPasswordReset(new_password=password_data.new_password),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserSchema.model_validate(updated)


@router.put("/me/avatar", response_model=UserSchema)
def update_avatar(
    avatar_update: UserAvatarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserSchema:
    """Update the current user's avatar URL."""
    updated = crud_update_user_avatar(
        db, user_id=current_user.id, avatar_url=str(avatar_update.avatar_url)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserSchema.model_validate(updated)
