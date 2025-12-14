import pytest
from pydantic import ValidationError

from taskmanagement_app.schemas.user import (
    AdminUserCreate,
    UserCreate,
    UserPasswordReset,
    UserUpdate,
)


def test_password_strength_valid() -> None:
    valid = UserPasswordReset(new_password="Str0ng!Pass")
    assert valid.new_password == "Str0ng!Pass"


def test_password_strength_missing_uppercase() -> None:
    with pytest.raises(ValidationError):
        UserPasswordReset(new_password="weakpass1!")


def test_password_strength_missing_lowercase() -> None:
    with pytest.raises(ValidationError):
        UserPasswordReset(new_password="WEAKPASS1!")


def test_password_strength_missing_digit() -> None:
    with pytest.raises(ValidationError):
        UserPasswordReset(new_password="WeakPass!!")


def test_password_strength_missing_special() -> None:
    with pytest.raises(ValidationError):
        UserPasswordReset(new_password="WeakPass11")


def test_password_strength_min_length() -> None:
    with pytest.raises(ValidationError):
        UserPasswordReset(new_password="S1!a")


def test_user_create_schema() -> None:
    user = UserCreate(email="test@example.com", password="Str0ng!Pass")
    assert user.email == "test@example.com"
    assert user.password == "Str0ng!Pass"


def test_admin_user_create_schema() -> None:
    admin = AdminUserCreate(
        email="admin@example.com", password="Str0ng!Pass", is_admin=True
    )
    assert admin.email == "admin@example.com"
    assert admin.is_admin is True


def test_user_update_schema() -> None:
    update = UserUpdate(
        email="new@example.com",
        is_active=False,
        avatar_url="/a.png",
        password="NewP@ssw0rd",
    )
    assert update.email == "new@example.com"
    assert update.is_active is False
    assert update.avatar_url == "/a.png"
    assert update.password == "NewP@ssw0rd"
