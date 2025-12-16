from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from taskmanagement_app.core.auth import (
    create_admin_user_token,
    create_superadmin_token,
    create_user_token,
)
from taskmanagement_app.core.config import get_settings
from taskmanagement_app.core.security import verify_password
from taskmanagement_app.crud.user import get_user_by_email, update_last_login
from taskmanagement_app.db.session import get_db
from taskmanagement_app.schemas.token import Token

router = APIRouter()
settings = get_settings()


@router.post("/user/token", response_model=Token)
async def login_user_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    if (
        form_data.username == settings.ADMIN_USERNAME
        and form_data.password == settings.ADMIN_PASSWORD
    ):
        access_token = create_superadmin_token(
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return Token(access_token=access_token, token_type="bearer")

    user = get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    update_last_login(db, user.id)

    if user.is_admin:
        access_token = create_admin_user_token(
            subject=user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    else:
        access_token = create_user_token(
            subject=user.email,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    return Token(access_token=access_token, token_type="bearer")
