"""User schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None
    password: Optional[str] = None


class AdminUserCreate(UserCreate):
    """Schema for admin creating a new user."""

    is_admin: bool = False


class UserPasswordReset(BaseModel):
    """Schema for resetting a user's password."""

    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:'\",.<>/?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class User(UserBase):
    """Schema for user responses."""

    id: int
    is_active: bool
    is_admin: bool
    avatar_url: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
