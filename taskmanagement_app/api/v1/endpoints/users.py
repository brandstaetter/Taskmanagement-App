from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import verify_access_token
from taskmanagement_app.core.security import get_password_hash, verify_password
from taskmanagement_app.crud.user import get_user_by_email
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.user import (
    User as UserSchema,
    UserAvatarUpdate,
    UserPasswordChange,
)

router = APIRouter()


def get_current_user(
    payload: dict = Depends(verify_access_token), db: Session = Depends(get_db)
):
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
    current_user=Depends(get_current_user),
) -> UserSchema:
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    db.refresh(current_user)
    return UserSchema.model_validate(current_user)


@router.put("/me/avatar", response_model=UserSchema)
def update_avatar(
    avatar_update: UserAvatarUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> UserSchema:
    current_user.avatar_url = str(avatar_update.avatar_url)
    db.commit()
    db.refresh(current_user)
    return UserSchema.model_validate(current_user)
