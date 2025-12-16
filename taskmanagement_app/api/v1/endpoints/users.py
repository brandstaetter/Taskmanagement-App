from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import verify_access_token
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


def get_current_user(
    payload: dict[str, Any] = Depends(verify_access_token),
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
