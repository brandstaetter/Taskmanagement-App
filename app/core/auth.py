from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from app.core.config import get_settings

settings = get_settings()

# OAuth2 scheme for JWT tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# API Key header scheme for admin endpoints
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

def create_admin_token(expires_delta: Optional[timedelta] = None) -> str:
    """Create a new admin JWT token."""
    to_encode = {"sub": "admin", "role": "admin"}
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def verify_admin(
    token: str = Depends(oauth2_scheme),
    api_key: Optional[str] = Security(api_key_header)
) -> bool:
    """
    Verify that the request is from an admin.
    Accepts either a valid JWT token with admin role or the admin API key.
    """
    # First check API key if provided
    if api_key:
        if api_key == settings.ADMIN_API_KEY:
            return True
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key"
        )

    # If no API key, check JWT token
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        role: str = payload.get("role")
        if role is None or role != "admin":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return True

# Dependency for admin-only endpoints
require_admin = Security(verify_admin)
