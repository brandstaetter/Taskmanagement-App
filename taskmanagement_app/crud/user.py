"""User CRUD operations."""

import logging
import secrets
import string
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from taskmanagement_app.core.security import get_password_hash
from taskmanagement_app.db.models.user import User
from taskmanagement_app.schemas.user import (
    AdminUserCreate,
    UserCreate,
    UserPasswordReset,
    UserUpdate,
)

logger = logging.getLogger(__name__)


def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: UserCreate) -> User:
    """Create a new user."""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def admin_create_user(db: Session, user: AdminUserCreate) -> User:
    """Admin creates a new user."""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        is_admin=user.is_admin,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user: UserUpdate) -> Optional[User]:
    """Update user."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user.model_dump(exclude_unset=True)

    # Handle password update separately
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def generate_random_password(length: int = 12) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in string.punctuation for c in password)
        ):
            return password


def reset_user_password(
    db: Session, user_id: int
) -> Tuple[Optional[User], Optional[str]]:
    """Reset user's password to a random string."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None, None

    new_password = generate_random_password()
    db_user.hashed_password = get_password_hash(new_password)
    db.commit()
    db.refresh(db_user)
    return db_user, new_password


def change_user_password(
    db: Session, user_id: int, password_data: UserPasswordReset
) -> Optional[User]:
    """Change user's password to a specific string."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    db_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_last_login(db: Session, user_id: int) -> Optional[User]:
    """Update user's last login timestamp."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    db_user.last_login = datetime.now()
    db.commit()
    db.refresh(db_user)
    return db_user


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get all users with pagination."""
    return db.query(User).offset(skip).limit(limit).all()
