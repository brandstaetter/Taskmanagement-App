from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from taskmanagement_app.crud import user as user_crud
from taskmanagement_app.db.session import SessionLocal
from taskmanagement_app.schemas.user import (
    AdminUserCreate,
    UserCreate,
    UserPasswordReset,
    UserUpdate,
)


@pytest.fixture
def db():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


def test_create_user(db):
    data = UserCreate(email="u1@example.com", password="StrongPass1!")
    created = user_crud.create_user(db, data)
    assert created.email == data.email
    assert created.id is not None
    assert created.hashed_password != data.password
    assert created.is_active is True
    assert created.is_admin is False
    assert created.avatar_url is None
    db.delete(created)
    db.commit()


def test_admin_create_user(db):
    data = AdminUserCreate(
        email="admin2@example.com", password="AdminPass2@", is_admin=True
    )
    created = user_crud.admin_create_user(db, data)
    assert created.is_admin is True
    db.delete(created)
    db.commit()


def test_get_user_by_email(db):
    data = UserCreate(email="u2@example.com", password="StrongPass2!")
    created = user_crud.create_user(db, data)
    found = user_crud.get_user_by_email(db, data.email)
    assert found is not None
    assert found.id == created.id
    db.delete(created)
    db.commit()


def test_update_user(db):
    data = UserCreate(email="u3@example.com", password="StrongPass3!")
    created = user_crud.create_user(db, data)
    update = UserUpdate(
        email="u3b@example.com", is_active=False, avatar_url="/avatar.png"
    )
    updated = user_crud.update_user(db, created.id, update)
    assert updated is not None
    assert updated.email == "u3b@example.com"
    assert updated.is_active is False
    assert updated.avatar_url == "/avatar.png"
    db.delete(updated)
    db.commit()


def test_change_user_password(db):
    unique_email = f"u4_{uuid4()}@example.com"
    data = UserCreate(email=unique_email, password="StrongPass4!")
    created = user_crud.create_user(db, data)
    old_hashed_password = created.hashed_password
    reset = UserPasswordReset(new_password="NewPass4!")
    changed = user_crud.change_user_password(db, created.id, reset)
    assert changed is not None
    assert changed.hashed_password != old_hashed_password
    db.delete(changed)
    db.commit()


def test_reset_user_password(db):
    data = UserCreate(email="u5@example.com", password="StrongPass5!")
    created = user_crud.create_user(db, data)
    user, new_pw = user_crud.reset_user_password(db, created.id)
    assert user is not None
    assert new_pw is not None
    db.delete(user)
    db.commit()


def test_update_last_login(db):
    data = UserCreate(email="u6@example.com", password="StrongPass6!")
    created = user_crud.create_user(db, data)
    user = user_crud.update_last_login(db, created.id)
    assert user is not None
    assert isinstance(user.last_login, datetime)
    db.delete(user)
    db.commit()


def test_get_all_users(db):
    users = []
    for i in range(3):
        data = UserCreate(email=f"bulkuser{i}@example.com", password="BulkPass1!")
        users.append(user_crud.create_user(db, data))
    all_users = user_crud.get_all_users(db)
    emails = [u.email for u in all_users]
    for u in users:
        assert u.email in emails
    for u in users:
        db.delete(u)
    db.commit()


def test_unique_email_constraint(db):
    unique_email = f"unique_{uuid4()}@example.com"
    data = UserCreate(email=unique_email, password="UniquePass1!")
    user1 = user_crud.create_user(db, data)
    with pytest.raises(IntegrityError):
        user_crud.create_user(db, data)
    db.rollback()  # Roll back after IntegrityError
    db.delete(user1)
    db.commit()
