from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from taskmanagement_app.core.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/user/token")


def create_admin_token(expires_delta: Optional[timedelta] = None) -> str:
    """Create a new admin JWT token."""
    to_encode: dict[str, Any] = {"sub": "admin", "role": "admin"}
    if expires_delta:
        expire = datetime.now(tz=timezone.utc) + expires_delta
    else:
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    # Ensure we always return a str, regardless of platform
    return str(encoded_jwt)


def create_superadmin_token(expires_delta: Optional[timedelta] = None) -> str:
    to_encode: dict[str, Any] = {
        "sub": settings.ADMIN_USERNAME,
        "role": "superadmin",
    }
    if expires_delta:
        expire = datetime.now(tz=timezone.utc) + expires_delta
    else:
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return str(encoded_jwt)


def create_admin_user_token(
    subject: str, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode: dict[str, Any] = {"sub": subject, "role": "admin"}
    if expires_delta:
        expire = datetime.now(tz=timezone.utc) + expires_delta
    else:
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return str(encoded_jwt)


def create_user_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode: dict[str, Any] = {"sub": subject, "role": "user"}
    if expires_delta:
        expire = datetime.now(tz=timezone.utc) + expires_delta
    else:
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return str(encoded_jwt)


def verify_access_token(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("exp") is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def verify_admin(payload: dict[str, Any] = Depends(verify_access_token)) -> bool:
    """
    Verify that the request is from an admin.
    Returns True if valid, raises HTTPException if not.
    """
    role: Optional[str] = payload.get("role")
    if role is None or role not in {"admin", "superadmin"}:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


async def verify_superadmin(
    payload: dict[str, Any] = Depends(verify_access_token),
) -> bool:
    role: Optional[str] = payload.get("role")
    if role is None or role != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


async def verify_admin_only(
    payload: dict[str, Any] = Depends(verify_access_token),
) -> bool:
    role: Optional[str] = payload.get("role")
    if role is None or role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


async def verify_not_superadmin(
    payload: dict[str, Any] = Depends(verify_access_token),
) -> dict[str, Any]:
    role: Optional[str] = payload.get("role")
    if role is None or role == "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# Dependency for admin-only endpoints
require_admin = Depends(verify_admin)

require_superadmin = Depends(verify_superadmin)
require_admin_only = Depends(verify_admin_only)
require_not_superadmin = Depends(verify_not_superadmin)
